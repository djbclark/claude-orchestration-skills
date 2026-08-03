#!/usr/bin/env python3
"""Maintain the durable handoff log for a workspace.

The program deliberately has no hook-style error suppression: a failed git
command, malformed input, or unwritable state directory is an invocation
error and must be visible to its caller.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml


LOG_NAME = "SESSION_LOG.md"
HISTORY_HEADING = "## Recent History"
CURRENT_HEADING = "## Current State"


@dataclass
class HistoryEntry:
    timestamp: str
    writer: str
    lines: list[str]


def now_stamp() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def run_git(repo_dir: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo_dir, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout.strip()


def repository_state(repo_dir: Path) -> tuple[str, str, bool]:
    head = run_git(repo_dir, "rev-parse", "HEAD")
    try:
        branch = run_git(repo_dir, "symbolic-ref", "--short", "HEAD")
    except subprocess.CalledProcessError:
        branch = "HEAD"
    dirty = bool(run_git(repo_dir, "status", "--porcelain"))
    return branch, head, dirty


def split_document(text: str) -> tuple[dict[str, Any], str]:
    """Return YAML frontmatter and the markdown following it."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    raw = text[4:end]
    parsed = yaml.safe_load(raw) or {}
    if not isinstance(parsed, dict):
        raise ValueError("frontmatter must be a mapping")
    return parsed, text[end + 5 :]


def parse_history(body: str) -> list[HistoryEntry]:
    if HISTORY_HEADING not in body:
        return []
    history = body.split(HISTORY_HEADING, 1)[1]
    entries: list[HistoryEntry] = []
    current: HistoryEntry | None = None
    for line in history.splitlines():
        if line.startswith("### ") and " — " in line:
            stamp, writer = line[4:].split(" — ", 1)
            current = HistoryEntry(stamp.strip(), writer.strip(), [])
            entries.append(current)
        elif current is not None:
            current.lines.append(line)
    # Trailing blank lines are formatting, not entry content.
    for entry in entries:
        while entry.lines and not entry.lines[-1].strip():
            entry.lines.pop()
    return entries


def parse_timestamp(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None


def retain(entries: list[HistoryEntry]) -> list[HistoryEntry]:
    cutoff = datetime.now().astimezone() - timedelta(days=30)
    kept: list[HistoryEntry] = []
    for entry in entries:
        stamp = parse_timestamp(entry.timestamp)
        # An unparseable legacy timestamp is retained; silently deleting it is
        # worse than allowing a human to repair it.
        if stamp is not None:
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=cutoff.tzinfo)
            if stamp < cutoff:
                continue
        kept.append(entry)
        if len(kept) == 10:
            break
    return kept


def list_sidecars(state_dir: Path) -> list[Path]:
    return sorted(state_dir.glob("precompact-*.md"), key=lambda p: p.name)


def sidecar_entries(state_dir: Path) -> tuple[list[HistoryEntry], list[Path]]:
    """Make one history record per compaction, and list all files to remove."""
    files = list_sidecars(state_dir)
    by_name = {p.name: p for p in files}
    consumed: set[str] = set()
    entries: list[HistoryEntry] = []
    to_delete: list[Path] = []
    for path in files:
        if path.name in consumed:
            continue
        enriched_suffix = "-enriched.md"
        if path.name.endswith(enriched_suffix):
            base_name = path.name[: -len(enriched_suffix)] + ".md"
            if base_name in by_name:
                # The ordinary sidecar produces the record and points at this.
                continue
        companion = by_name.get(path.stem + "-enriched.md")
        frontmatter, body = split_document(path.read_text())
        timestamp = str(frontmatter.get("updated_at") or now_stamp())
        trigger = str(frontmatter.get("trigger") or "unknown")
        lines = [f"- unplanned compaction ({trigger})."]
        summary = " ".join(line.strip() for line in body.splitlines() if line.strip())
        if summary:
            lines.append(f"- Sidecar summary: {summary}")
        if companion is not None:
            lines.append(f"- Enriched sidecar summary: {companion.read_text().strip()}")
            consumed.add(companion.name)
            to_delete.append(companion)
        entries.append(HistoryEntry(timestamp, "compaction", lines))
        consumed.add(path.name)
        to_delete.append(path)
    return entries, to_delete


def render(frontmatter: dict[str, Any], active_work: str, blockers: list[str],
           next_steps: list[str], entries: list[HistoryEntry]) -> str:
    values: list[str] = ["---"]
    ordered = ("schema_version", "updated_at", "session_id", "writer", "workspace",
               "repo", "branch", "head_sha", "dirty", "chain", "latest_handoff")
    for key in ordered:
        if key not in frontmatter or frontmatter[key] is None:
            continue
        value = frontmatter[key]
        if isinstance(value, bool):
            value = "true" if value else "false"
        elif isinstance(value, list):
            value = "[" + ", ".join(str(item) for item in value) + "]"
        values.append(f"{key}: {value}")
    values.extend(["---", "", CURRENT_HEADING, f"- Active work: {active_work}"])
    values.append("- Blockers: " + ("; ".join(blockers) if blockers else "None"))
    values.append("- Next steps:")
    values.extend(f"  - {step}" for step in next_steps)
    values.extend(["", HISTORY_HEADING])
    for entry in entries:
        values.append(f"### {entry.timestamp} — {entry.writer}")
        values.extend(entry.lines or ["- No details recorded."])
        values.append("")
    return "\n".join(values).rstrip() + "\n"


def atomic_write(path: Path, content: str) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".session_log_", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def require_payload(raw: str) -> dict[str, Any]:
    data = json.loads(raw)
    required = ("session_id", "writer", "chain", "latest_handoff", "active_work",
                "blockers", "next_steps", "history_bullets")
    if not isinstance(data, dict) or any(key not in data for key in required):
        raise ValueError("payload is missing required fields")
    for key in ("session_id", "writer", "latest_handoff", "active_work"):
        if not isinstance(data[key], str):
            raise ValueError(f"payload {key} must be a string")
    for key in ("chain", "blockers", "next_steps", "history_bullets"):
        if not isinstance(data[key], list) or not all(isinstance(item, str) for item in data[key]):
            raise ValueError(f"payload {key} must be a list of strings")
    if len(data["history_bullets"]) > 3:
        raise ValueError("history_bullets may contain at most 3 items")
    return data


def read_command(state_dir: Path, repo_dir: Path) -> None:
    path = state_dir / LOG_NAME
    actual_head = run_git(repo_dir, "rev-parse", "HEAD")
    sidecars = [str(p) for p in list_sidecars(state_dir)]
    if not path.exists():
        print(json.dumps({"exists": False, "frontmatter": None, "body": "", "stale": None,
                          "actual_head": actual_head, "sidecars": sidecars}))
        return
    frontmatter, body = split_document(path.read_text())
    print(json.dumps({"exists": True, "frontmatter": frontmatter, "body": body,
                      "stale": frontmatter.get("head_sha") != actual_head,
                      "actual_head": actual_head, "sidecars": sidecars}))


def write_command(state_dir: Path, repo_dir: Path, raw: str) -> None:
    payload = require_payload(raw)
    path = state_dir / LOG_NAME
    old_frontmatter, old_body = split_document(path.read_text()) if path.exists() else ({}, "")
    branch, head_sha, dirty = repository_state(repo_dir)
    folded, deletions = sidecar_entries(state_dir)
    frontmatter = dict(old_frontmatter)
    frontmatter.update({"schema_version": 1, "updated_at": now_stamp(),
                        "session_id": payload["session_id"], "writer": payload["writer"],
                        "branch": branch, "head_sha": head_sha, "dirty": dirty,
                        "chain": payload["chain"], "latest_handoff": payload["latest_handoff"]})
    # Keep the history heading independently timestamped.  Besides describing
    # the event more precisely, this avoids conflating a document update with
    # its entry when an operator edits a historical heading by hand.
    entry_stamp = (datetime.now().astimezone() + timedelta(seconds=1)).strftime(
        "%Y-%m-%dT%H:%M:%S%z")
    new_entry = HistoryEntry(entry_stamp, payload["writer"],
                             [f"- {line}" for line in payload["history_bullets"]])
    entries = retain([new_entry, *folded, *parse_history(old_body)])
    atomic_write(path, render(frontmatter, payload["active_work"], payload["blockers"],
                              payload["next_steps"], entries))
    for sidecar in deletions:
        sidecar.unlink()


def fold_command(state_dir: Path, repo_dir: Path) -> None:
    # Validate repo input consistently with other commands, without modifying
    # recorded repository state.
    run_git(repo_dir, "rev-parse", "HEAD")
    path = state_dir / LOG_NAME
    if not path.exists():
        raise FileNotFoundError(f"cannot fold sidecars: {path} does not exist")
    frontmatter, body = split_document(path.read_text())
    folded, deletions = sidecar_entries(state_dir)
    frontmatter["updated_at"] = now_stamp()
    # Current State is retained verbatim in fold mode.
    current = body.split(HISTORY_HEADING, 1)[0]
    entries = retain([*folded, *parse_history(body)])
    history_lines = [HISTORY_HEADING]
    for entry in entries:
        history_lines.extend([f"### {entry.timestamp} — {entry.writer}", *entry.lines, ""])
    content = render_frontmatter_and_body(frontmatter, current.rstrip(), "\n".join(history_lines))
    atomic_write(path, content)
    for sidecar in deletions:
        sidecar.unlink()


def render_frontmatter_and_body(frontmatter: dict[str, Any], current: str, history: str) -> str:
    # Reuse render's frontmatter serialization while deliberately preserving
    # Current State byte-for-byte (apart from unavoidable surrounding newlines).
    prefix = render(frontmatter, "", [], [], []).split(CURRENT_HEADING, 1)[0]
    return prefix + current.lstrip("\n") + "\n" + history.rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("read", "write", "fold"))
    parser.add_argument("--dir", required=True, type=Path)
    parser.add_argument("--repo-dir", required=True, type=Path)
    args = parser.parse_args()
    if not args.dir.is_dir():
        raise NotADirectoryError(args.dir)
    if args.command == "read":
        read_command(args.dir, args.repo_dir)
    elif args.command == "write":
        write_command(args.dir, args.repo_dir, sys.stdin.read())
    else:
        fold_command(args.dir, args.repo_dir)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"session_log.py: {error}", file=sys.stderr)
        raise SystemExit(1)
