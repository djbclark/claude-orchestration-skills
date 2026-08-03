---
name: session-handoff
description: Read/write an out-of-tree Tier 1 session pointer file (SESSION_LOG.md) for a task workspace. Use at session start, before handing off to another agent/session, and at session end. Triggers on: resume session, session log, tier 1, read the session log, update session log.
---

# Session Handoff — Tier 1 pointer file

A cheap, out-of-tree pointer file that lets a fresh session (or the same
session after compaction) recover where a piece of work stands without
re-deriving it from scratch. Companion skill `handoff` (this same
plugin) covers the deeper Tier 2 recovery document for substantial work.

**Path convention (adapt to your own layout):** `~/.local/state/handoffs/<repo>/<task>/SESSION_LOG.md`,
where `<task>` is the task-workspace directory name under wherever you
keep per-task git worktrees (this reference implementation assumes
`~/src/ops-worktrees/<task>/<repo>`, using `main` for a shared reference
checkout and `ops`/similar for a deploy checkout — rename to match your
own convention). The state root lives outside any git tree on purpose:
in-worktree state dangles across `git checkout` and is destroyed by
`git worktree remove`; decoupling the file's lifetime from the
worktree's removes both failure classes.

## Ownership

One writer per task workspace: the session that owns it. Sub-agents
NEVER write Tier 1 or Tier 2 — they return completion reports; the owner
writes. Any agent may read.

## Reader protocol (session start, or when handed a Tier 1 path)

1. Read `SESSION_LOG.md` if present. Also glob `precompact-*.md` in the
   same dir — sidecars newer than `updated_at` are unplanned-compaction
   checkpoints (written by the `precompact_handoff.py` hook, this same
   plugin's `hooks/`) that supersede the log's recency.
2. Staleness check: compare frontmatter `head_sha` to actual
   `git rev-parse HEAD` in the worktree. Mismatch (or dirty-state drift)
   demotes the file from briefing to lead: verify its claims against the
   repo before trusting any of them.
3. State a resume plan to the operator BEFORE touching anything.
4. Never ask the operator for information the file already answers.
5. File missing or unparseable: not an error. Bootstrap a minimal one
   from `git status` / `git log -1` / current branch with Active work:
   "no prior context found", then proceed.

## Writer protocol (before handoff, at session end, after major state changes)

Use the helper — it owns caps, sidecar folding, atomicity, and git
anchoring so you don't have to get them right by hand:

    <path-to-tools-venv>/bin/python <path-to-tools>/session_log.py write \
      --dir <state-dir> --repo-dir <worktree>

with the JSON payload on stdin (`session_id`, `writer`, `chain`,
`latest_handoff`, `active_work`, `blockers`, `next_steps`,
`history_bullets` — max 3). `read` and `fold` subcommands exist too;
`read` returns the staleness verdict pre-computed. `session_log.py` and
its test suite live in this plugin's `tools/` directory; set up a venv
with `pyyaml`, `anyio`, and `claude-agent-sdk` (only needed if you also
wire up the optional enrichment hook) per `tools/pyproject.toml`. Only
edit the file by hand if the helper is broken, and then follow the same
rules it enforces (replace Current State wholesale; 10-entry/30-day/
3-bullet caps; temp-file + rename).

Composition rule regardless of path: every Next-steps item must be a
path, a runnable command, or an ID resolvable from cold start. Never
"as discussed above"; never a bare reference to tool-backed state (task
lists, memory) without the exact tool call that retrieves it.

## File format

    ---
    schema_version: 1
    updated_at: 2026-08-03T14:22:17-0400
    session_id: <pane id, session uuid, or "solo">
    writer: claude-code
    workspace: <task dir name>
    repo: <repo name>
    branch: <branch>
    head_sha: <full sha>
    dirty: true|false
    chain: [<issue/epic ids or standalone-hex>]
    latest_handoff: <path to a Tier 2 doc, or "none">
    ---

    ## Current State
    - Active work: <issue ID + description, or free text>
    - Blockers: <list or "None">
    - Next steps: <bullets per writer-protocol rule 6>

    ## Recent History
    ### 2026-08-03T14:22:17-0400 — claude-code
    - <max 3 bullets>

## Guards

- Only operate under your recognized task-workspace roots (see the path
  convention above). Elsewhere: this skill does not apply; say so and
  stop.
- Deep recovery (chain-tagged docs, full conversation mining) is the
  separate `handoff` skill (Tier 2). This skill is the cheap pointer
  only.

## The PreCompact hook (optional, `hooks/precompact_handoff.py`)

Register it in `PreCompact` (see your tool's hook-registration docs).
It reads the hook's JSON stdin, resolves the current directory against
the path convention above, and — if it resolves — writes a standalone
`precompact-<utc-ts>.md` sidecar next to `SESSION_LOG.md` (branch,
`head_sha`, dirty-file list, trigger) via an atomic temp-file+rename. It
is a pure safety net: it never edits `SESSION_LOG.md` itself, and it
**must always exit 0** — a hook that can fail or delay a compaction is
worse than no hook. Outside the recognized path roots it's a silent
no-op, so it's safe to register globally.

Optional: after writing the sidecar, it fires one *detached* background
process (never blocking the hook) that uses the Claude Agent SDK with a
cheap/fast model to mine the session's transcript (path supplied in the
hook's own JSON input) into a `*-enriched.md` companion — goal, failed
approaches, decisions, measurements, next steps. This is the one piece
that spends model quota; kill switch is the `HANDOFF_ENRICH=0`
environment variable, checked before anything is spawned. The hook
script itself stays dependency-free (stdlib only) on purpose — it must
keep working even if the tools venv is broken; the SDK and other
dependencies live only in `tools/`, which the hook merely shells out to
if present.
