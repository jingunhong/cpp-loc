"""Report sources: link parsers and fetchers behind one on-disk cache.

A source finds its references in a commit message (``refs``) and turns one reference into
a report (``report`` -> ``(title, body, extra_metadata)`` or a drop reason). Raw responses
are cached as JSON under ``<cache_dir>/<source>/`` (``null`` for 404), so a re-run with a
warm cache is offline and deterministic. Fetching is stdlib ``urllib`` with retries and
rate-limit sleeps; nothing here is called from the tests over the network.
"""

import base64
import email
import email.policy
import hashlib
import html
import http.client
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from . import filters

Report = tuple[str, str, dict]  # title, body, extra metadata (always carries report_url)
_QUOTE_RE = re.compile(r"^\s*>")
_PATCH_SUBJECT_RE = re.compile(r"^\s*\[[^\]]*\bpatch\b", re.IGNORECASE)  # not "Re: [PATCH"


def http_get(
    url: str, headers: dict[str, str] | None = None, pace: float = 0.0, not_found=(404,)
) -> bytes | None:
    """GET ``url``; None for a ``not_found`` status. Retries transient errors and 5xx with
    exponential backoff, sleeps through 403/429 rate limits (``*RateLimit-Reset`` epoch or
    60 s), and pauses ``pace`` seconds after every successful request."""
    req = urllib.request.Request(url, headers={"User-Agent": "cpp-loc", **(headers or {})})
    for attempt in range(8):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                if urllib.parse.urlsplit(resp.url).netloc == "accounts.google.com":
                    return None  # login-only page (syzkaller private namespace): not found
                data = resp.read()
                if (
                    resp.headers.get(
                        "X-RateLimit-Remaining", resp.headers.get("RateLimit-Remaining", "1")
                    )
                    == "0"
                ):
                    _sleep_until_reset(resp.headers)
            time.sleep(pace)
            return data
        except urllib.error.HTTPError as e:
            if e.code in not_found:
                return None
            if e.code in (403, 429):
                _sleep_until_reset(e.headers)
            elif e.code >= 500:
                time.sleep(2**attempt)
            else:
                raise
        except urllib.error.URLError, http.client.HTTPException, TimeoutError:
            time.sleep(2**attempt)  # transient network error, retry with backoff
    raise RuntimeError(f"giving up on {url} after 8 attempts")


def _sleep_until_reset(headers) -> None:
    reset = int(headers.get("X-RateLimit-Reset", headers.get("RateLimit-Reset", "0")))
    time.sleep(max(reset - time.time(), 60))


def clean_body(text: str) -> str:
    """Mail body without quoted lines (``> ...``) and without the ``-- `` signature block;
    runs of blank lines collapsed."""
    kept = []
    for line in text.splitlines():
        if line == "-- ":  # the signature marker is dash-dash-space; a bare "--" is log text
            break
        if not _QUOTE_RE.match(line):
            kept.append(line.rstrip())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


def html_to_text(fragment: str) -> str:
    """``<br>`` and ``</p>`` become newlines, other tags are dropped, entities unescaped."""
    text = re.sub(r"<br\s*/?>", "\n", fragment)
    text = re.sub(r"</p>", "\n\n", text)
    return html.unescape(re.sub(r"<[^>]+>", "", text))


def _unique(items) -> list[str]:
    return list(dict.fromkeys(items))


class Source:
    """Base: ``refs``/``fetch``/``parse`` per source; caching and drop reasons shared."""

    name = ""
    pace = 0.5  # seconds between requests; polite default for sites without a limit header
    headers: dict[str, str] = {}
    not_found = (404,)

    def __init__(self, cache_dir: Path, subdir: str | None = None, *, offline: bool = False):
        self.cache_dir = cache_dir
        self.offline = offline
        self.consumed: dict[str, dict] = {}
        self.dir = cache_dir / (subdir or self.name)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.stats: Counter[str] = Counter()  # informational counters that are not drops

    def refs(self, message: str) -> list[str]:
        raise NotImplementedError

    def fetch(self, ref: str):
        """Raw JSON-serialisable response for ``ref``, or None when it does not exist."""
        raise NotImplementedError

    def parse(self, ref: str, raw) -> Report | str:
        """``(title, body, extra)`` from a cached raw response, or a drop reason."""
        raise NotImplementedError

    def cache_path(self, ref: str) -> Path:
        key = urllib.parse.quote(ref, safe="")
        if len(key) > 200:
            key = hashlib.sha1(ref.encode()).hexdigest()
        return self.dir / f"{key}.json"

    def get(self, ref: str):
        """Read cached bytes. Offline misses raise FileNotFoundError without a request.

        Old payloads are never rewritten or assigned invented fetch timestamps.
        New fetch sidecars contain only time and payload hash, never request headers.
        """
        path = self.cache_path(ref)
        sidecar = path.with_suffix(".fetch.json")
        if path.exists():
            data = path.read_bytes()
        else:
            if self.offline:
                self.stats["offline cache miss"] += 1
                raise FileNotFoundError(f"offline cache miss: {path.relative_to(self.cache_dir)}")
            raw = self.fetch(ref)
            data = json.dumps(raw).encode("utf-8")
            path.write_bytes(data)
            sidecar.write_text(
                json.dumps(
                    {
                        "fetched_at": datetime.now(UTC).isoformat(),
                        "sha256": hashlib.sha256(data).hexdigest(),
                    }
                )
                + "\n",
                encoding="utf-8",
            )
        digest = hashlib.sha256(data).hexdigest()
        fetch = json.loads(sidecar.read_text()) if sidecar.exists() else {}
        entry = {
            "path": path.relative_to(self.cache_dir).as_posix(),
            "sha256": digest,
            "bytes": len(data),
            "fetched_at": fetch.get("fetched_at") if fetch.get("sha256") == digest else None,
        }
        if sidecar.exists():
            entry["fetch_sidecar"] = {
                "path": sidecar.relative_to(self.cache_dir).as_posix(),
                "sha256": hashlib.sha256(sidecar.read_bytes()).hexdigest(),
            }
        self.consumed[entry["path"]] = entry
        return json.loads(data)

    def report(self, ref: str) -> Report | str:
        try:
            raw = self.get(ref)
        except FileNotFoundError:
            return "offline cache miss"
        parsed = "not found" if raw is None else self.parse(ref, raw)
        if isinstance(parsed, str):
            return parsed
        from .provenance import report_evidence

        title, body, extra = parsed
        return title, body, {**extra, "report_provenance": report_evidence(self, ref, raw, parsed)}

    def _json(self, url: str):
        data = http_get(url, self.headers, self.pace, self.not_found)
        return None if data is None else json.loads(data)

    def _text(self, url: str) -> str | None:
        data = http_get(url, self.headers, self.pace, self.not_found)
        return None if data is None else data.decode("utf-8", errors="replace")


class GitHub(Source):
    """``/repos/<upstream>/issues/<n>``; refs are issue numbers as strings. Without a token
    GitHub allows 60 requests/hour, so unauthenticated runs pause a second per call."""

    name = "github_issue"

    def __init__(self, cache_dir: Path, upstream: str, token: str | None):
        super().__init__(cache_dir, f"{self.name}/{upstream.replace('/', '__')}")
        self.upstream = upstream
        self.headers = {"Accept": "application/vnd.github+json"}
        self.pace = 1.0
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
            self.pace = 0.0

    def refs(self, message: str) -> list[str]:
        return [str(n) for n in filters.issue_refs(message, self.upstream)]

    def fetch(self, ref: str):
        return self._json(f"https://api.github.com/repos/{self.upstream}/issues/{ref}")

    def parse(self, ref: str, raw) -> Report | str:
        if "pull_request" in raw:
            return "reference is a pull request"
        if not (raw.get("title") or "").strip():
            return "issue has no title"
        extra = {
            "issue_number": int(ref),
            "issue_url": raw["html_url"],
            "report_url": raw["html_url"],
        }
        return raw["title"], raw.get("body") or "", extra


class GitLab(Source):
    """``https://gitlab.com/<project>/-/issues/N`` URLs anywhere in the message; public API,
    no auth (500 requests/minute, ``RateLimit-*`` headers)."""

    name = "gitlab_issue"
    pace = 0.15

    def __init__(self, cache_dir: Path, project: str):
        super().__init__(cache_dir)
        self.project = project

    def refs(self, message: str) -> list[str]:
        return gitlab_issue_refs(message, self.project)

    def fetch(self, ref: str):
        number = ref.rsplit("/", 1)[1]
        project = urllib.parse.quote(self.project, safe="")
        return self._json(f"https://gitlab.com/api/v4/projects/{project}/issues/{number}")

    def parse(self, ref: str, raw) -> Report | str:
        if not (raw.get("title") or "").strip():
            return "issue has no title"
        return raw["title"], raw.get("description") or "", {"report_url": raw.get("web_url", ref)}


def gitlab_issue_refs(message: str, project: str) -> list[str]:
    """``https://gitlab.com/<project>/-/issues/N`` URLs anywhere in the message, in order."""
    pattern = rf"https://gitlab\.com/{re.escape(project)}/-/issues/\d+\b"
    return _unique(re.findall(pattern, message))


class Syzbot(Source):
    """``syzbot+<hash>@syzkaller.appspotmail.com`` addresses and ``syzkaller.appspot.com/bug?``
    URLs anywhere in the message. Report = bug title + first crash report text."""

    name = "syzbot"
    pace = 3.0  # the dashboard throttles an IP at ~20 requests/minute (429, no headers)
    _REF_RE = re.compile(
        r"syzbot\+([0-9a-f]+)@syzkaller\.appspotmail\.com|syzkaller\.appspot\.com/bug\?((?:extid|id)=[0-9a-f]+)"
    )

    def refs(self, message: str) -> list[str]:
        return _unique(f"extid={m[1]}" if m[1] else m[2] for m in self._REF_RE.finditer(message))

    def fetch(self, ref: str):
        bug = self._json(f"https://syzkaller.appspot.com/bug?{ref}&json=1")
        if bug is None:
            return None
        crashes = bug.get("crashes") or []
        link = crashes[0].get("crash-report-link") if crashes else None
        report = self._text("https://syzkaller.appspot.com" + link) if link else None
        return {"bug": bug, "report": report}

    def parse(self, ref: str, raw) -> Report | str:
        title = (raw["bug"].get("title") or "").strip()
        if not title:
            return "empty report"
        return (
            title,
            raw["report"] or "",
            {"report_url": f"https://syzkaller.appspot.com/bug?{ref}"},
        )


class Lore(Source):
    """``Closes: https://lore.kernel.org/...`` (or lkml.kernel.org) trailers; the raw message
    at ``https://lore.kernel.org/all/<msgid>/raw``, cached as base64 of the raw bytes so the
    email library resolves charset and transfer encoding. Subject + body, quotes and
    signature stripped. A target whose subject is a ``[PATCH ...]`` post is a submission,
    not a report; a ``Re: [PATCH ...]`` reply is kept (a reviewer's report against a
    patch)."""

    name = "lore_report"
    _REF_RE = re.compile(r"^Closes:\s*(https?://(?:lore|lkml)\.kernel\.org/\S+)", re.MULTILINE)
    _MSGID_RE = re.compile(r"^https?://(?:lore|lkml)\.kernel\.org/[^/]+/([^/#\s]+)")

    def refs(self, message: str) -> list[str]:
        return _unique(m[1].rstrip(".:,;`'\"") for m in self._REF_RE.finditer(message))

    def fetch(self, ref: str):
        m = self._MSGID_RE.match(ref)
        if not m:
            return None
        data = http_get(
            f"https://lore.kernel.org/all/{m[1]}/raw", self.headers, self.pace, self.not_found
        )
        return None if data is None else base64.b64encode(data).decode("ascii")

    def parse(self, ref: str, raw) -> Report | str:
        msg = email.message_from_bytes(base64.b64decode(raw), policy=email.policy.default)
        subject = " ".join(str(msg.get("Subject", "")).split())
        if _PATCH_SUBJECT_RE.match(subject):
            return "target is a patch"
        part = msg.get_body(preferencelist=("plain",))
        try:  # strict: an undeclared charset with 8-bit text must reach the fallback
            body = part.get_content(errors="strict") if part else ""
        except LookupError, UnicodeDecodeError, KeyError:
            self.stats["charset fallback"] += 1
            body = (part.get_payload(decode=True) or b"").decode("utf-8", errors="replace")
        body = clean_body(body)
        if not subject and not body:
            return "empty report"
        return subject, body, {"report_url": ref, "report_kind": self.kind(ref, msg, subject, body)}

    @staticmethod
    def kind(ref: str, msg, subject: str, body: str) -> str:
        """``robot`` (kernel test robot / lkp by sender, list or body), ``reply`` (a
        ``Re: [...]`` reply to a posted patch) or ``fresh``."""
        sender = str(msg.get("From", ""))
        if (
            "lkp@intel.com" in sender
            or "/oe-kbuild-all/" in ref
            or "/oe-lkp/" in ref
            or "kernel test robot" in f"{sender}\n{body}".lower()
        ):
            return "robot"
        return "reply" if re.match(r"^Re:\s*\[", subject) else "fresh"


class Bugzilla(Source):
    """``bugzilla.kernel.org/show_bug.cgi?id=N`` URLs anywhere in the message (that host only
    serves bug reports); REST ``/rest/bug/N`` summary + first comment."""

    name = "kernel_bugzilla"
    not_found = (401, 404)  # 401: private bug
    _REF_RE = re.compile(r"https?://bugzilla\.kernel\.org/show_bug\.cgi\?id=(\d+)")

    def refs(self, message: str) -> list[str]:
        return _unique(m[0] for m in self._REF_RE.finditer(message))

    def fetch(self, ref: str):
        number = self._REF_RE.match(ref)[1]
        data = self._json(f"https://bugzilla.kernel.org/rest/bug/{number}")
        if not data or not data.get("bugs"):
            return None
        comments = self._json(f"https://bugzilla.kernel.org/rest/bug/{number}/comment") or {}
        first = (comments.get("bugs", {}).get(number, {}).get("comments") or [None])[0]
        return {"bug": data["bugs"][0], "comment": first}

    def parse(self, ref: str, raw) -> Report | str:
        title = (raw["bug"].get("summary") or "").strip()
        if not title:
            return "empty report"
        body = (raw["comment"] or {}).get("text") or ""
        return title, body, {"report_url": ref}


class PgArchive(Source):
    """``Discussion:`` archive URLs (postgr.es/m/<msgid> or postgresql.org/message-id/...).
    Fetches the flat thread page and picks (see :meth:`pick`) the first ``BUG #`` message,
    else the first reply to a ``pgsql:`` commit notification, else the linked message
    itself; body from the page's HTML, quotes and signature stripped. The archive's
    raw-message view redirects to HTML for non-browser clients."""

    name = "pgsql_archive"
    _REF_RE = re.compile(
        r"^Discussion:\s*(https?://(?:www\.)?(?:postgr\.es/m|postgresql\.org/message-id)/\S+)",
        re.MULTILINE,
    )
    _MSGID_RE = re.compile(r"(?:/m/|/message-id/(?:flat/)?)([^/#\s]+)")
    _MSG_RE = re.compile(
        r'<th scope="row">Subject:</th>\s*<td>(.*?)</td>.*?'
        r'<th scope="row">Message-ID:</th>\s*<td><a href="[^"]*">(.*?)</a>.*?'
        r'<div class="message-content">(.*?)</div>',
        re.DOTALL,
    )

    def refs(self, message: str) -> list[str]:
        return _unique(m[1].rstrip(".:,;)") for m in self._REF_RE.finditer(message))

    def fetch(self, ref: str):
        m = self._MSGID_RE.search(ref)
        if not m:
            return None
        msgid = urllib.parse.quote(urllib.parse.unquote(m[1]), safe="")
        return self._text(f"https://www.postgresql.org/message-id/flat/{msgid}")

    @classmethod
    def messages(cls, page: str) -> list[tuple[str, str, str]]:
        """``(subject, message_id, body_text)`` per message in thread order."""
        return [
            (html.unescape(s).strip(), html.unescape(i).strip(), html_to_text(b))
            for s, i, b in cls._MSG_RE.findall(page)
        ]

    @classmethod
    def pick(cls, messages: list[tuple[str, str, str]], linked: str) -> tuple[int, str] | str:
        """``(index, how)`` of the report in the flat thread, or a drop reason. ``how`` is
        ``bug_subject`` (first ``BUG #`` message), ``committers_reply`` (the thread root is
        a ``pgsql:`` commit notification: its first reply) or ``linked_message`` (the
        message the ``Discussion:`` URL points at, ``linked`` = its message-id)."""
        if not messages:
            return "no message on page"
        for i, (subject, _, _) in enumerate(messages):
            if subject.startswith("BUG #"):
                return i, "bug_subject"
        if messages[0][0].startswith("pgsql:"):
            if len(messages) == 1:
                return "committers thread without reply"
            return 1, "committers_reply"
        for i, (_, msgid, _) in enumerate(messages):
            if msgid == linked:
                return i, "linked_message"
        return "linked message not in thread"

    def parse(self, ref: str, raw) -> Report | str:
        messages = self.messages(raw)
        picked = self.pick(messages, urllib.parse.unquote(self._MSGID_RE.search(ref)[1]))
        if isinstance(picked, str):
            return picked
        index, how = picked
        subject, msgid, body = messages[index]
        body = clean_body(body)
        if not subject and not body:
            return "empty report"
        url = "https://www.postgresql.org/message-id/" + urllib.parse.quote(msgid, safe="")
        extra = {
            "report_url": url,
            "report_pick": how,
            "report_thread_root_subject": messages[0][0],
            "report_thread_position": index,
        }
        return subject, body, extra


# Reference kinds recorded in ``metadata.report_refs`` without a fetcher.
_LINK_RE = re.compile(r"^Link:\s*(\S+)", re.MULTILINE | re.IGNORECASE)
_LAUNCHPAD_RE = re.compile(r"https?://bugs\.launchpad\.net/qemu/\+bug/\d+")
_PG_BUG_RE = re.compile(r"^Bug:\s*#?(\d+)", re.MULTILINE)


def link_urls(message: str) -> list[str]:
    return _unique(m[1] for m in _LINK_RE.finditer(message))


def launchpad_refs(message: str) -> list[str]:
    return _unique(m[0] for m in _LAUNCHPAD_RE.finditer(message))


def pgsql_bug_refs(message: str) -> list[str]:
    return _unique(f"#{m[1]}" for m in _PG_BUG_RE.finditer(message))
