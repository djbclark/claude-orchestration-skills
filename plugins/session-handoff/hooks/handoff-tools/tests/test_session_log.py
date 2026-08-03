"""Contract tests for session_log.py. Tests ARE the spec where prose
is ambiguous. Run: .venv/bin/python -m pytest tests/ -q"""
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parent.parent / "session_log.py"


def run(args, stdin=None):
    return subprocess.run([sys.executable, str(TOOL), *args],
                          input=stdin, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=r, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "--allow-empty", "-m", "init"],
                   cwd=r, check=True)
    return r


@pytest.fixture
def state(tmp_path):
    s = tmp_path / "state"
    s.mkdir()
    return s


def payload(**kw):
    base = dict(session_id="s1", writer="claude-code", chain=["x-1"],
                latest_handoff="none", active_work="test work",
                blockers=[], next_steps=["run: echo hi"],
                history_bullets=["did a thing"])
    base.update(kw)
    return json.dumps(base)


def head(repo):
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                          capture_output=True, text=True).stdout.strip()


def test_read_missing_is_not_error(state, repo):
    p = run(["read", "--dir", str(state), "--repo-dir", str(repo)])
    assert p.returncode == 0
    assert json.loads(p.stdout)["exists"] is False


def test_write_then_read_roundtrip(state, repo):
    p = run(["write", "--dir", str(state), "--repo-dir", str(repo)],
            stdin=payload())
    assert p.returncode == 0, p.stderr
    log = state / "SESSION_LOG.md"
    assert log.exists()
    text = log.read_text()
    assert "schema_version: 1" in text
    assert head(repo) in text
    out = json.loads(run(["read", "--dir", str(state),
                          "--repo-dir", str(repo)]).stdout)
    assert out["exists"] and out["stale"] is False


def test_staleness_flips_after_new_commit(state, repo):
    run(["write", "--dir", str(state), "--repo-dir", str(repo)],
        stdin=payload())
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "--allow-empty", "-m", "move"],
                   cwd=repo, check=True)
    out = json.loads(run(["read", "--dir", str(state),
                          "--repo-dir", str(repo)]).stdout)
    assert out["stale"] is True
    assert out["actual_head"] == head(repo)


def test_history_cap_10_entries(state, repo):
    for i in range(13):
        run(["write", "--dir", str(state), "--repo-dir", str(repo)],
            stdin=payload(history_bullets=[f"entry {i}"]))
    text = (state / "SESSION_LOG.md").read_text()
    assert text.count("### ") == 10
    assert "entry 12" in text and "entry 2" not in text


def test_max_3_bullets_rejected(state, repo):
    p = run(["write", "--dir", str(state), "--repo-dir", str(repo)],
            stdin=payload(history_bullets=["a", "b", "c", "d"]))
    assert p.returncode != 0


def test_sidecars_folded_and_deleted(state, repo):
    (state / "precompact-20260803T120000Z.md").write_text(
        "---\ncompacted: true\ntrigger: manual\n"
        "updated_at: 2026-08-03T08:00:00-0400\n---\n\nclean\n")
    run(["write", "--dir", str(state), "--repo-dir", str(repo)],
        stdin=payload())
    text = (state / "SESSION_LOG.md").read_text()
    assert "unplanned compaction" in text
    assert not list(state.glob("precompact-*.md"))


def test_current_state_replaced_wholesale(state, repo):
    run(["write", "--dir", str(state), "--repo-dir", str(repo)],
        stdin=payload(active_work="OLD WORK"))
    run(["write", "--dir", str(state), "--repo-dir", str(repo)],
        stdin=payload(active_work="NEW WORK"))
    text = (state / "SESSION_LOG.md").read_text()
    assert "NEW WORK" in text
    # old value survives only in history, never in Current State
    cs = text.split("## Recent History")[0]
    assert "OLD WORK" not in cs


def test_atomic_no_tmp_litter(state, repo):
    run(["write", "--dir", str(state), "--repo-dir", str(repo)],
        stdin=payload())
    assert not [p for p in state.iterdir() if ".tmp" in p.name]


def test_age_cap_30_days(state, repo):
    old = (datetime.now().astimezone() - timedelta(days=45))
    stamp = old.strftime("%Y-%m-%dT%H:%M:%S%z")
    run(["write", "--dir", str(state), "--repo-dir", str(repo)],
        stdin=payload(history_bullets=["ancient"]))
    text = (state / "SESSION_LOG.md").read_text()
    text = text.replace(
        text.split("### ")[1].split(" — ")[0], stamp, 1)
    (state / "SESSION_LOG.md").write_text(text)
    run(["write", "--dir", str(state), "--repo-dir", str(repo)],
        stdin=payload(history_bullets=["fresh"]))
    final = (state / "SESSION_LOG.md").read_text()
    assert "fresh" in final and "ancient" not in final
