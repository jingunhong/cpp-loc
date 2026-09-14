import base64
import json
from collections import Counter
from pathlib import Path

import pytest

from cpp_loc import extract, filters, reports
from tests.test_schema import make

LINUX = """\
mm/mremap: reset unfaulted VMA page offset

Reported-by: syzbot+f12658786a4153df5113@syzkaller.appspotmail.com
Closes: https://syzkaller.appspot.com/bug?extid=f12658786a4153df5113
Reported-by: kernel test robot <lkp@intel.com>
Closes: https://lore.kernel.org/oe-kbuild-all/202401011234.abcd-lkp@intel.com/
Closes: https://lore.kernel.org/r/20260608025043.88087-1-cuiyunhui@bytedance.com.
Closes: https://lore.kernel.org/netdev/CAHk-=wg@mail.gmail.com/T/#u
Closes: https://bugzilla.kernel.org/show_bug.cgi?id=221485
Link: https://bugzilla.kernel.org/show_bug.cgi?id=218000#c14
Link: https://lore.kernel.org/r/20240101-fix-v1-1-abc@kernel.org
Tested-by: syzbot+d6dd6f86d3aaf7eebe74@syzkaller.appspotmail.com
Signed-off-by: A <a@x>
"""
SYZ_ID = "d6dd6f86d3aaf7eebe7406e45c1c6e549453f224"


@pytest.fixture
def cache(tmp_path: Path) -> Path:
    return tmp_path / "cache"


def test_linux_ref_parsers(cache: Path):
    syz, lore, bz = reports.Syzbot(cache), reports.Lore(cache), reports.Bugzilla(cache)
    assert syz.refs(LINUX) == ["extid=f12658786a4153df5113", "extid=d6dd6f86d3aaf7eebe74"]
    assert syz.refs(f"Closes: https://syzkaller.appspot.com/bug?id={SYZ_ID}") == [f"id={SYZ_ID}"]
    assert lore.refs(LINUX) == [
        "https://lore.kernel.org/oe-kbuild-all/202401011234.abcd-lkp@intel.com/",
        "https://lore.kernel.org/r/20260608025043.88087-1-cuiyunhui@bytedance.com",
        "https://lore.kernel.org/netdev/CAHk-=wg@mail.gmail.com/T/#u",
    ]
    assert lore._MSGID_RE.match(lore.refs(LINUX)[2])[1] == "CAHk-=wg@mail.gmail.com"
    assert bz.refs(LINUX) == [
        "https://bugzilla.kernel.org/show_bug.cgi?id=221485",
        "https://bugzilla.kernel.org/show_bug.cgi?id=218000",
    ]
    assert reports.link_urls(LINUX) == [
        "https://bugzilla.kernel.org/show_bug.cgi?id=218000#c14",
        "https://lore.kernel.org/r/20240101-fix-v1-1-abc@kernel.org",
    ]


def test_qemu_and_postgres_ref_parsers(cache: Path):
    qemu = (
        "hw/ide: fix\n\nResolves: https://gitlab.com/qemu-project/qemu/-/issues/4038\n"
        "Fixes: https://gitlab.com/qemu-project/qemu/-/issues/4038\n"
        "Buglink: https://bugs.launchpad.net/qemu/+bug/1234\n"
        "Resolves: https://gitlab.com/other/proj/-/issues/1\nResolves: Coverity CID 1\n"
    )
    issue = "https://gitlab.com/qemu-project/qemu/-/issues/4038"
    assert reports.gitlab_issue_refs(qemu, "qemu-project/qemu") == [issue]
    assert reports.GitLab(cache, "qemu-project/qemu").refs(qemu) == [issue]
    assert reports.launchpad_refs(qemu) == ["https://bugs.launchpad.net/qemu/+bug/1234"]
    pg = (
        "Fix bug\n\nBug: #19441\n"
        "Discussion: https://postgr.es/m/19441-ec29f3b1363b4a68@postgresql.org\n"
        "Discussion: https://www.postgresql.org/message-id/flat/19637-4446f7%40postgresql.org\n"
        "Discussion: http://postgr.es/m/abc@x.\nBackpatch-through: 13\n"
    )
    src = reports.PgArchive(cache)
    assert src.refs(pg) == [
        "https://postgr.es/m/19441-ec29f3b1363b4a68@postgresql.org",
        "https://www.postgresql.org/message-id/flat/19637-4446f7%40postgresql.org",
        "http://postgr.es/m/abc@x",
    ]
    ids = [src._MSGID_RE.search(r)[1] for r in src.refs(pg)]
    assert ids == [
        "19441-ec29f3b1363b4a68@postgresql.org",
        "19637-4446f7%40postgresql.org",
        "abc@x",
    ]
    assert reports.pgsql_bug_refs(pg) == ["#19441"]
    assert reports.pgsql_bug_refs("Bug: 17654\n") == ["#17654"]


def _pg_message(subject: str, msgid: str, body_html: str) -> str:
    return (
        f'<a name="{msgid}"></a><table class="message-header"><tr><th scope="row">From:</th>'
        f'<td>X</td></tr><tr><th scope="row">Subject:</th>\n  <td>{subject}</td></tr>'
        f'<tr><th scope="row">Message-ID:</th>\n  <td><a href="/message-id/x">{msgid}</a></td>'
        f'</tr></table>\n<div class="message-content">{body_html}</div>\n'
    )


def test_pg_pick_bug_subject_committers_reply_linked_message(cache: Path):
    bug_body = (
        "<p>The following bug has been logged:</p><p>&gt; quoted<br>step 1<br>step &amp; 2</p>"
    )
    page = (
        _pg_message("Patch v1", "a@x", "<p>see patch</p>")
        + _pg_message("BUG #19441: hang", "19441-x@postgresql.org", bug_body + "<p>-- <br>sig</p>")
        + _pg_message("Re: BUG #19441: hang", "b@x", "<p>reply</p>")
    )
    src = reports.PgArchive(cache)
    msgs = src.messages(page)
    assert [m[0] for m in msgs] == ["Patch v1", "BUG #19441: hang", "Re: BUG #19441: hang"]
    assert src.pick(msgs, "b@x") == (1, "bug_subject")  # BUG # wins over the linked message
    assert src.parse("https://postgr.es/m/b@x", page) == (
        "BUG #19441: hang",
        "The following bug has been logged:\n\nstep 1\nstep & 2",
        {
            "report_url": "https://www.postgresql.org/message-id/19441-x%40postgresql.org",
            "report_pick": "bug_subject",
            "report_thread_root_subject": "Patch v1",
            "report_thread_position": 1,
        },
    )
    # a pgsql-committers notification as root: its first reply is the report
    commit = _pg_message("pgsql: Fix planner", "E1@gemulon.postgresql.org", "<p>Fix planner</p>")
    reply = _pg_message("Re: pgsql: Fix planner", "r@x", "<p>this broke my query</p>")
    got = src.parse("https://postgr.es/m/E1%40gemulon.postgresql.org", commit + reply)
    assert got[0] == "Re: pgsql: Fix planner"
    assert got[2] == {
        "report_url": "https://www.postgresql.org/message-id/r%40x",
        "report_pick": "committers_reply",
        "report_thread_root_subject": "pgsql: Fix planner",
        "report_thread_position": 1,
    }
    no_reply = src.parse("https://postgr.es/m/E1%40gemulon.postgresql.org", commit)
    assert no_reply == "committers thread without reply"
    # otherwise the linked message itself, not the thread root
    thread = (
        _pg_message("Planner crash", "root@x", "<p>root</p>")
        + _pg_message("Re: Planner crash", "r%40x", "<p>re</p>")
        + _pg_message("Re: Planner crash", "third@x", "<p>third</p>")
    )
    got = src.parse("https://www.postgresql.org/message-id/flat/r%2540x", thread)
    assert (got[1], got[2]["report_pick"], got[2]["report_thread_position"]) == (
        "re",
        "linked_message",
        1,
    )
    assert src.parse("https://postgr.es/m/root@x", thread)[2]["report_thread_position"] == 0
    assert src.parse("https://postgr.es/m/zzz@x", thread) == "linked message not in thread"
    assert src.parse("https://postgr.es/m/x@y", "<html></html>") == "no message on page"


def _mail(raw: str | bytes) -> str:
    """The lore cache entry: base64 of the raw message bytes."""
    return base64.b64encode(raw if isinstance(raw, bytes) else raw.encode()).decode()


def test_lore_parse_strips_quotes_and_rejects_patches(cache: Path):
    raw = _mail(
        "From: R <r@x>\nSubject: [bug report] foo: null deref\n  in bar()\n"
        "Content-Type: text/plain\n\n"
        "Hi,\n\nOn Mon, X wrote:\n> old\n> lines\n\nfoo crashes.\n\n\n\nMore.\n-- \nsig\n"
    )
    src = reports.Lore(cache)
    assert src.parse("https://lore.kernel.org/r/a@b", raw) == (
        "[bug report] foo: null deref in bar()",
        "Hi,\n\nOn Mon, X wrote:\n\nfoo crashes.\n\nMore.",
        {"report_url": "https://lore.kernel.org/r/a@b", "report_kind": "fresh"},
    )
    for subject in ("[PATCH v2 1/3] mm: fix", "[RFC PATCH] x", "[PATCH net-next] y"):
        assert src.parse("u", _mail(f"Subject: {subject}\n\nbody\n")) == "target is a patch"
    reply = _mail("Subject: Re: [PATCH v2] x\n\nthis breaks boot\n")
    assert src.parse("u", reply)[0] == "Re: [PATCH v2] x"
    only_quotes = _mail("Subject: [syzbot] KASAN: x\n\n> only quotes\n")
    assert src.parse("u", only_quotes)[:2] == ("[syzbot] KASAN: x", "")


def test_lore_report_kind(cache: Path):
    src = reports.Lore(cache)

    def kind(ref: str, raw: str) -> str:
        return src.parse(ref, _mail(raw))[2]["report_kind"]

    robot_from = "From: kernel test robot <lkp@intel.com>\nSubject: [x] warning\n\nb\n"
    assert kind("u", robot_from) == "robot"
    lkp_list = "https://lore.kernel.org/oe-kbuild-all/2024@intel.com/"
    assert kind(lkp_list, "From: X <x@y>\nSubject: s\n\nb\n") == "robot"
    robot_body = "From: Bot <bot@x>\nSubject: Re: [PATCH] x\n\nHi,\n\nkernel test robot noticed\n"
    assert kind("u", robot_body) == "robot"
    assert kind("u", "From: H <h@x>\nSubject: Re: [PATCH v3 2/2] mm: x\n\nthis breaks\n") == "reply"
    assert kind("u", "From: H <h@x>\nSubject: Re:[PATCH] x\n\nb\n") == "reply"
    assert kind("u", "From: H <h@x>\nSubject: [BUG] oops in foo\n\nb\n") == "fresh"
    assert kind("u", "From: H <h@x>\nSubject: Re: oops in foo\n\nb\n") == "fresh"


def test_lore_parse_resolves_charsets_and_transfer_encodings(cache: Path):
    src = reports.Lore(cache)
    latin1 = _mail(
        b"Subject: =?iso-8859-1?q?Hellstr=F6m_report?=\n"
        b"Content-Type: text/plain; charset=iso-8859-1\nContent-Transfer-Encoding: 8bit\n\n"
        b"Thomas Hellstr\xf6m saw it.\n"
    )
    assert src.parse("u", latin1)[:2] == ("Hellström report", "Thomas Hellström saw it.")
    qp = _mail(
        b"Subject: qp\nContent-Type: text/plain; charset=utf-8\n"
        b"Content-Transfer-Encoding: quoted-printable\n\n=D0=B3=D0=B4=D0=B5 crash =3D bad\n"
    )
    assert src.parse("u", qp)[1] == "где crash = bad"
    assert src.stats == {}
    undeclared = _mail(b"Subject: raw\n\nna\xc3\xafve 8-bit without a charset\n")
    assert src.parse("u", undeclared)[1] == "naïve 8-bit without a charset"
    assert src.stats == {"charset fallback": 1}
    assert "\\u" not in src.parse("u", qp)[1] and "\ufffd" not in src.parse("u", latin1)[1]


def test_clean_body_signature_marker_is_dash_dash_space():
    log = "WARNING at x\n--\n[ 1.0] still the log\n-- \nsig line\n"
    assert reports.clean_body(log) == "WARNING at x\n--\n[ 1.0] still the log"
    assert reports.clean_body("a\n--\nb\n") == "a\n--\nb"


def test_syzbot_bugzilla_gitlab_github_parse(cache: Path):
    syz = reports.Syzbot(cache)
    raw = {"bug": {"title": "WARNING in vma_set_pgoff"}, "report": "------------[ cut here ]"}
    assert syz.parse("extid=f1", raw) == (
        "WARNING in vma_set_pgoff",
        "------------[ cut here ]",
        {"report_url": "https://syzkaller.appspot.com/bug?extid=f1"},
    )
    assert syz.parse("extid=f1", {"bug": {"title": ""}, "report": None}) == "empty report"
    bz = reports.Bugzilla(cache)
    with_comment = {"bug": {"summary": "s"}, "comment": {"text": "c"}}
    assert bz.parse("u", with_comment) == ("s", "c", {"report_url": "u"})
    assert bz.parse("u", {"bug": {"summary": "s"}, "comment": None})[1] == ""
    gl = reports.GitLab(cache, "qemu-project/qemu")
    issue = {"title": "t", "description": None, "web_url": "w"}
    assert gl.parse("u", issue) == ("t", "", {"report_url": "w"})
    gh = reports.GitHub(cache, "o/r", token=None)
    assert (cache / "github_issue/o__r").is_dir()
    assert gh.refs("Fixes #12, closes: #7") == ["12", "7"]
    assert filters.issue_refs("Fixes #12", "o/r") == [12]
    assert gh.parse("7", {"title": "PR", "pull_request": {}}) == "reference is a pull request"
    assert gh.parse("9", {"title": " Crash ", "body": " when x \n", "html_url": "u9"}) == (
        " Crash ",
        " when x \n",
        {"issue_number": 9, "issue_url": "u9", "report_url": "u9"},
    )


class Fake(reports.Syzbot):
    def __init__(self, cache_dir, responses):
        super().__init__(cache_dir)
        self.responses, self.calls = responses, []

    def fetch(self, ref):  # no network
        self.calls.append(ref)
        return self.responses[ref]


def test_cache_and_add_reports(cache: Path):
    src = Fake(cache, {"extid=aa": None, "extid=bb": {"bug": {"title": "T"}, "report": "R"}})
    assert src.report("extid=aa") == "not found"
    assert src.report("extid=aa") == "not found"  # second call served from the cache
    assert json.loads((cache / "syzbot/extid%3Daa.json").read_text()) is None
    assert src.calls == ["extid=aa"]

    hit = make(problem_statement=None, problem_source=None)
    hit.metadata["report_refs"] = {"syzbot": ["extid=aa", "extid=bb"]}
    miss = make(problem_statement=None, problem_source=None)
    miss.metadata["report_refs"] = {"syzbot": ["extid=aa"]}
    none = make(problem_statement=None, problem_source=None)
    none.metadata["report_refs"] = {}
    drops: Counter[str] = Counter()
    extract.add_reports([hit, miss, none], [src], drops)
    assert (hit.problem_statement, hit.problem_source) == ("T\n\nR", "syzbot")
    assert hit.metadata["report_url"] == "https://syzkaller.appspot.com/bug?extid=bb"
    assert hit.metadata["report_kind"] is None
    assert miss.problem_statement is None and miss.problem_source is None
    assert none.problem_statement is None
    assert drops == {"syzbot: not found": 2}
    assert all(i.validate() == [] for i in (hit, miss, none))


def test_http_get_treats_login_redirect_as_not_found(monkeypatch):
    class Resp:
        url = "https://accounts.google.com/v3/signin/identifier?continue=x"
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def read(self):
            raise AssertionError("must not read a sign-in page")

    monkeypatch.setattr(reports.urllib.request, "urlopen", lambda req, timeout: Resp())
    assert reports.http_get("https://syzkaller.appspot.com/bug?extid=x&json=1") is None
