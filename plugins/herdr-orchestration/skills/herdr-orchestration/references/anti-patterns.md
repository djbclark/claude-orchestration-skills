# Anti-patterns (things that went wrong once, don't repeat)

- Trusting a sub-agent's "CI passes" / "verified" claim without checking —
  led to shipping-adjacent PRs with a real regression that a cosmetic-looking
  fix had glossed over.
- Writing "hand off to Agent N+1 the way this handoff to you was made" into a
  sub-agent's prompt — ambiguous enough to read as "use herdr yourself,"
  which is exactly what the [core rule](../SKILL.md#core-rule-only-the-orchestrator-orchestrates) forbids. Say plainly: prepare
  your handoff (plan file + clipboard prompt per the existing protocol), the
  orchestrator will launch the next one.
- Re-enabling a disabled billing/credits toggle to get access to a better
  model, on the theory that "the operator said make the best call" — that
  authority covers model/vendor/effort selection, not spend-control settings.
- Assuming a model name from an older plan/roster still exists — check the
  live picker.
- **Moving on while a sub-agent's PR sits unmerged "pending operator review."**
  With merge authority, the merge step is yours: review and merge the unit's
  PR before starting the next unit, or write down why not and when you'll
  revisit it (see ["Workflow per unit"](../SKILL.md#workflow-per-unit) steps 9-11). Otherwise PRs with no owner
  pile up unnoticed, foundational fixes included.
- **Trusting "local check passes" without confirming it actually ran
  everything.** A sub-agent's worktree missing supporting tools/venvs makes
  its own check script *silently skip* the exact checks that matter (lint,
  format, test-collection) instead of failing — the sub-agent's "CI passes
  locally" report is then genuinely true of what ran, and still worthless.
  Before trusting a green local run, either reproduce it yourself with the
  full toolchain installed, or at minimum grep its output for
  "skip"/"not installed" next to anything load-bearing.
- **Closing your own tab/pane during a bulk cleanup loop.** Check each target
  against `$HERDR_TAB_ID`/`$HERDR_PANE_ID` before closing it. The self-closure
  wrapper and the `orc` naming convention exist to stop this; don't remove
  either without replacing that protection.
- **Not reading a new script's own logic just because it has passing
  tests.** A sub-agent's new notification script called a CLI subcommand
  that doesn't exist (silently a no-op) instead of the one actually
  confirmed working earlier in the same session, and separately had a
  guaranteed false-positive bug — neither one was caught by its own tests,
  because the tests were written by the same pass that missed the bugs.
  Read new orchestrator-facing code (notifications, checks, anything meant
  to fire unattended later) line by line once, independent of its test
  suite.
