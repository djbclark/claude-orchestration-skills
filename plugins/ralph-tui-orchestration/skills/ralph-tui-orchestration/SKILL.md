---
name: ralph-tui-orchestration
description: Operate a Ralph TUI + Beads multi-repo controller system — seeding tasks, going live with a controller for the first time, and the safety discipline that catches near-misses before they cause real damage. Use when asked to run/seed/check a Ralph controller, or when setting up Ralph TUI for a new project.
---

# Ralph TUI orchestration

Built from real sessions running Ralph TUI + Beads (`bd`) + Beads Viewer
(`bv`) controllers across multiple repos, including a real near-miss (an
agent nearly took a destructive action against an explicitly hands-off
checkout) caught the same day it happened.

**Keep your own technical reference doc** for exact paths, epic IDs, and
config schema specific to your setup — this skill is the behavioral layer
on top: what to actually *do* when seeding or running a controller,
independent of your specific repos.

## Gate prepaid-balance agent vendors — never usable without asking first

If any of the agent vendors you configure for Ralph TUI are billed against a
prepaid balance rather than an included subscription quota, gate them.
Ralph TUI's agent config has no native per-invocation confirmation
mechanism — a normal `[[agents]]` entry just runs when selected, with no
way to pause and ask a human first. Don't rely on a config comment saying
"ask before using this"; that's not a real gate, it only works as long as
nobody forgets.

The pattern that works: point the agent's `command` at a wrapper script
instead of the real CLI binary. The wrapper refuses to invoke the real CLI
unless an explicit environment variable is set in the process that spawns
it (e.g. `ALLOW_PREPAID_SPEND=1`), printing a clear error and exiting
non-zero otherwise. Never set that variable on the operator's behalf, and
never treat a prior approval as covering a later, different task — ask
fresh every time, no matter how routine it seems. **Verify the gate
actually blocks before trusting it** — run the CLI (or `ralph-tui doctor
--agent <name>`) with the variable deliberately unset and confirm you get
a clean refusal with zero real API calls, not just read the wrapper source
and assume it works. This mirrors the same "never select a usage-credits-
backed model without asking" rule that applies to interactive Herdr
orchestration too — same principle, same reason (real money, not included
usage), just enforced at a different layer since Ralph TUI and Herdr spawn
agents differently.

## The one rule everything else follows from

**Task scope is the real safety control, not a human approval gate.**
`autoCommit` stays `false` and controllers run autonomously; the thing
that keeps a run safe is a tightly-scoped task description the agent
reads and follows — not someone watching every action. This means task
authoring quality *is* the safety mechanism. Write every task like it's
the only thing standing between the agent and doing something you didn't
intend, because it is.

## Before any first-time live run for a controller

1. **Epic-based scoping only — never rely on labels for task selection.**
   `bv --robot-next`/`--robot-triage` have been confirmed (as of the last
   check) to silently ignore `--label` — check the project's own issue
   tracker for current status before trusting label-based filtering. Every
   controller's `.ralph-tui/config.toml` should set
   `trackers.options.epicId` to that repo's controller epic. Labels stay on
   tasks as human-readable metadata only.
2. **Every task must carry its own scope constraints in its own
   description**, not just in your memory of what it should do. Explicitly
   state: what NOT to touch (name specific files/dirs/checkouts if
   relevant), whether code changes are allowed at all, what the deliverable
   is (a comment? which issue?), and whether it may close anything. A task
   seeded without this is the actual attack surface — an agent with real
   tool access will use it if the task doesn't say not to.
3. **If an epic could have more than one ready task and one of them must
   not be picked** (e.g. a permanently hands-off tracking task sitting
   under the same epic as a real one), don't trust `bv`'s scoring to land
   on the right one. Temporarily defer the one that must not be picked
   (`bd update <id> --defer <date>` or equivalent) **before starting the
   run, not mid-session** — a defer applied after a run has already begun
   can be ignored by that same run's task-selection on a later iteration
   (confirmed: a task deferred mid-session got re-picked twice more before
   the run was manually stopped; the identical defer applied before a
   fresh run started was respected correctly from the first iteration
   onward). Confirm only the intended task shows as ready, run the
   controller, then **restore the deferred task afterward** — verify it's
   back to its normal state, not left in limbo.
4. **Watch the first iteration and verify the picked task ID yourself**
   against `bd list --parent <epicId>` (or `bd show <task-id>` — confirm
   its `PARENT` line matches) *before* letting the agent proceed past task
   selection. This is not optional the first time a controller goes live,
   or after any change to how it's invoked. This exact check is what
   catches a wrong-task-picked near-miss — a clean exit code looks fine
   without it.

## After any run, live or otherwise

**Verify the real outcome directly — don't trust Ralph's own status
report in either direction.** Two confirmed failure modes:

- **False positive**: a clean exit / `COMPLETED` status does not by
  itself prove the agent did the right thing (it can mean "picked the
  wrong task and completed *that* cleanly").
- **False negative**: Ralph's own session report can say `Status:
  INTERRUPTED` / `Tasks: 0/1 completed` for a run that actually finished
  correctly — the internal `iterations[].status` can say `"completed"`
  while the top-level summary disagrees. Confirmed on a real run: the
  actual work (`bd` bead closed with a real close reason, real GitHub
  comment posted, clean git tree) was fully correct despite the
  alarming-looking status.

The only reliable check is independent, every time:
- `bd show <task-id>` — is it closed, with a real `close_reason` that
  actually describes what happened (not a placeholder)?
- `git status --short` in the controller's task workspace — clean if the
  task was research-only, or a real diff matching what the task asked for
  if it wasn't.
- If the task's deliverable was a GitHub comment/issue/PR: `gh issue
  view`/`gh pr view` directly — does the comment exist, with the right
  timestamp and content, on the right issue, in the right state (still
  open if the task said not to close it)?

## Where controllers run

Run every controller from a dedicated task workspace on its own branch —
**never** the shared reference checkout your other tooling reads from. The
moment `parallel.mode` is enabled, Ralph forces `autoCommit: true` per
worker, and running from a shared checkout would put that directly on your
main branch with no PR/review step. Keep the shared reference checkout
clean and untouched for everything else; give each controller its own
isolated worktree/branch instead.

## Seeding a good first validation task

A pattern that works cleanly: pick a real, existing, small piece of
backlog (an open GitHub issue is ideal — gives a natural deliverable
target and a natural "don't close it" boundary), scope it as
**research/recommendation only, no code changes, no destructive actions**,
and require the finding be posted somewhere checkable (a GitHub comment,
or a `bd comment` on the task itself if there's no corresponding issue
yet). This is genuinely useful output, not busywork, and it's the safest
possible shape for a controller's first live run in a repo.

## External actions (GitHub comments/issues/PRs)

Decide up front whether you want a separate review gate beyond
`autoCommit`, or whether a well-scoped controller should act autonomously
on external, visible actions too (same philosophy as `autoCommit` itself).
Either way, this makes task authoring (point 2 above) the real thing
standing between a controller and an external, visible, permanent action —
don't get casual about scoping a task just because local commits feel like
the only thing that matters.

## Review-gate tasks can get short-circuited

A real case: a task instructed a controller to (1) try triggering an
automated review directly on a PR the operator doesn't have review-bot
access to (predictably gets no response), (2) as the actual fix, obtain a
real review through some other in-scope mechanism and apply the findings
back, then (3) do an independent secondary review as a fallback signal.
What actually happened: the agent tried step 1, saw no response, and
jumped straight to step 3 — skipping step 2 entirely. The deliverable (a
real review comment posted on the PR) looked satisfied, and the "verify
independently" check above (`bd show`, `gh pr view`) confirmed a real
review *was* posted — so this specific gap wasn't caught by that check,
only by manually re-reading whether every described step actually
happened, not just whether *a* deliverable existed matching the task's
close reason.

**Lesson: a prose-sequenced task description with a fallback step is an
invitation to skip the harder intermediate step once the fallback looks
available.** If an intermediate step is load-bearing (not optional, not
just a nice-to-have), say so explicitly — "step 2 is not optional even if
step 1 fails, do not skip to step 3" — and prefer a single concrete
command over multi-step prose the agent has to interpret and sequence
itself, since a paragraph can be partially skipped in a way a single
command invocation can't. If this is a recurring need, it's worth building
the multi-step mechanism into a real tool with one entry point, rather
than re-describing the steps in prose in every task that needs it.

## Orchestrating a controller through Herdr

If you're driving a controller from a separate orchestrator session via
Herdr (see the `herdr-orchestration` skill for the general mechanics),
expect `herdr agent prompt` to intermittently leave text sitting
unsubmitted in the composer (`agent_prompt_stalled`, or the text visibly
sitting after a placeholder like `[Pasted text #N]`) — check Herdr's own
issue tracker for current status on this before assuming it's fixed.
Workaround: `herdr agent send-keys <name> enter` immediately after a
stall, then re-check status. Don't mistake old unsubmitted composer text
for something mysterious — check `herdr agent read` before assuming
anything more concerning is going on.
