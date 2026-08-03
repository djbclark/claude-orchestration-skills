# claude-orchestration-skills

Claude Code skills for orchestrating multi-agent work via [Herdr](https://herdr.dev)
and [Ralph TUI](https://github.com/subsy/ralph-tui) + [Beads](https://github.com/gastownhall/beads).

These are the behavioral/discipline layer on top of those tools' own
mechanics — what to actually *do* when spawning, monitoring, and verifying
a chain of sub-agents, and the real failure modes (near-misses, false
status reports, silently-skipped steps) that motivated each rule.

## Install

```
/plugin marketplace add djbclark/claude-orchestration-skills
/plugin install herdr-orchestration@claude-orchestration-skills
/plugin install ralph-tui-orchestration@claude-orchestration-skills
/plugin install session-handoff@claude-orchestration-skills
```

`session-handoff` additionally ships actual code (a hook script and a
small CLI), not just skill docs — see its section below for setup.

## What's here

- **`herdr-orchestration`** — driving a multi-agent handoff chain directly
  via [Herdr](https://herdr.dev) (a terminal multiplexer for coding
  agents) instead of relaying prompts through a human pasting into fresh
  windows. Covers: the orchestrator-only-orchestrates rule, self-closure
  defense, pane layout conventions, per-tool yolo-mode flags, and a list
  of anti-patterns from real sessions.
- **`ralph-tui-orchestration`** — operating a
  [Ralph TUI](https://github.com/subsy/ralph-tui) + [Beads](https://github.com/gastownhall/beads)
  multi-repo controller system. Covers: task-scope-as-safety-control (the
  core design principle), first-run verification discipline, independent
  outcome verification (Ralph's own status reports can be wrong in both
  directions), and a real near-miss that shaped the whole approach.

Neither skill requires the other, but they compose well if you're running
Ralph TUI controllers and also orchestrating ad hoc agent chains through
Herdr for work Ralph doesn't cover.

- **`session-handoff`** — durable session continuity across compaction
  and cold starts: a cheap out-of-tree Tier 1 pointer file per task
  workspace (git-SHA-anchored, staleness-checkable), an optional deeper
  Tier 2 recovery document for substantial work, and a `PreCompact` hook
  that writes a crash-safe checkpoint sidecar before any compaction
  (with best-effort transcript enrichment via a cheap model, gated by an
  environment-variable kill switch). Unlike the other two skills, this
  one isn't a wrapper around an external product — it ships the actual
  hook script and CLI tooling (`plugins/session-handoff/hooks/`,
  `plugins/session-handoff/tools/`). Installing the plugin gets you the
  skill docs; you still need to copy or symlink `hooks/precompact_handoff.py`
  into your Claude Code hooks directory and register it under
  `PreCompact` in `settings.json` yourself, and set up `tools/` (a
  Python 3.10+ venv per `tools/pyproject.toml`) if you want the
  `session_log.py` helper or transcript enrichment. The path
  conventions in the skill docs (`~/.local/state/handoffs/`,
  `~/src/ops-worktrees/<task>/<repo>`) are this reference
  implementation's own layout — adapt them to yours.

## Why these exist

Both were extracted from real multi-agent orchestration sessions —
genericized from the incidents, near-misses, and confirmed bugs that
actually happened, not written speculatively. Where a lesson only makes
sense with a specific example, the example is anonymized but kept
concrete (constructed scenarios don't teach the same lesson as "this
actually happened and here's exactly how").

## License

MIT — see [LICENSE](./LICENSE).
