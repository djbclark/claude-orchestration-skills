---
name: herdr-orchestration
description: Drive a multi-agent handoff chain (e.g. a plan file listing sequential units of work for different AI tools/models) directly via Herdr instead of human-relayed clipboard handoffs. Use when the user asks to "continue handling handoffs yourself", "orchestrate the next agent", or references an orchestration plan file with a self-perpetuation protocol meant for human relay. Only the main session orchestrates — spawned sub-agents never launch further agents themselves.
---

# Herdr multi-agent orchestration

Built from real sessions driving multi-agent handoff chains directly via
Herdr instead of relaying prompts through a human pasting into fresh tool
windows. Use this whenever the main Claude Code session is asked to take
over spawning and monitoring a sequence of agent units itself.

**Load the `herdr` skill first** (the vendor-shipped skill covering the
underlying CLI primitives: panes, tabs, `agent start`/`prompt`/`wait`/
`read`). This skill is the orchestration layer on top of that.

## Core rule: only the orchestrator orchestrates

You (the main session) are the only thing that decides what happens next and
launches it. A sub-agent's own task prompt must never instruct it to use
Herdr to spawn its successor itself — even a plan file's own built-in
self-perpetuation protocol (check off a row, copy a prompt to the clipboard,
print a status line) is fine to leave in a sub-agent's instructions, since
that's just clipboard prep, not a herdr call — but never write "use herdr to
start Agent N+1" into a sub-agent's prompt. When a sub-agent finishes, you
read its output, verify it, decide the next unit and model yourself, and
launch it yourself.

## Session-to-session handoffs: prefer live orchestration over clipboard relay

**If `HERDR_ENV=1` and the `herdr` binary responds, don't hand off via
`pbcopy` + "go paste this into a fresh window."** Spawn and configure the
next session yourself: split a pane, `herdr agent start <name> --kind claude
-- --model <alias> --effort <level>`, then `herdr agent prompt <name>
"<handoff text>" --wait`. This isn't just tidier — it's more reliable. A
live Herdr pane can be corrected in the moment (see the `[Pasted text #1]`
resend-Enter step further down), monitored for a wrong turn before it
compounds, and re-prompted immediately with a precise correction. A
clipboard-pasted handoff into a manually-opened window has none of that:
if the new session misreads the handoff, the operator has to notice, relay
the correction back by hand, and round-trips get slow. Only fall back to
a clipboard/`pbcopy` handoff when Herdr genuinely isn't available (a
separate machine, a human-only channel, or the operator explicitly wants a
manually-started window) — check the environment first rather than
defaulting to clipboard out of habit.

**A real failure this surfaced, worth designing every handoff prompt
around:** a handoff prompt referenced a Claude Code task-tracking entry by
a bare ID (e.g. "task #46"). The fresh session that received it via
clipboard tried to look this up with shell commands, found nothing (task
state isn't a file it can `grep` for — it's backed by tool calls that may
be deferred and need loading before they're callable), and confidently
reported a plausible-sounding but false conclusion instead of recognizing
its own lookup had failed. The task was still there the entire time,
unchanged, one tool call away. **Any handoff prompt that references
harness-internal state (task IDs, memory files, session IDs) must say
explicitly which tool retrieves it**, not just cite a bare ID — and should
include a snapshot of the current content inline as a fallback, so a
failed live lookup doesn't strand the receiving session with nothing. More
generally: give absolute filesystem paths (not `~`), full URLs (not
shorthand like `repo#N`), and spell out tool-vs-shell-vs-file distinctions
for anything that isn't obviously one or the other — a fresh session has
no assumed familiarity with what's a tool call, what's a real file, and
what's ephemeral session state, and will guess if you don't say.

### Durable file backing (Tier 1/Tier 2 handoff systems)

Live orchestration works best on top of a durable, file-based
session-handoff system: a cheap, out-of-tree "Tier 1" pointer file per
task workspace (current state, next steps, a git-SHA anchor for
staleness detection), and optionally a deeper "Tier 2" recovery document
for substantial work. If your setup has one:

- BEFORE spawning or prompting the next session, the owning session
  updates Tier 1 — and writes a Tier 2 doc if the work is substantial
  enough to deserve deep recovery.
- The spawn prompt is a **bootstrap packet**, not a context dump:
  1. repo + absolute workspace path
  2. one-line objective
  3. absolute path to the Tier 1 pointer file
  4. instruction: "Report whether that file exists and whether its
     recorded git SHA matches the actual current HEAD before doing
     anything else."
  5. a 2–3 line critical-fallback summary in case the path is wrong.
- Sub-agents never write Tier 1/Tier 2; they end by returning a
  completion report (what changed, commands run, blockers) and the
  owner folds it into Tier 1.

## Orchestrator tab identity and self-closure defense

**The orchestrator's own herdr tab must be named `orc`.** At the start of any
orchestration session, check your own tab's label:

```bash
herdr tab list --workspace "$HERDR_WORKSPACE_ID" | grep "$HERDR_TAB_ID"
```

If it isn't already `orc`, rename it yourself before doing anything else:

```bash
herdr tab rename "$HERDR_TAB_ID" orc
```

This exists so the orchestrator's own seat is unmistakable at a glance (and
identifiable programmatically) across a session with a dozen-plus sub-agent
tabs — never rely on remembering a raw tab ID or "whichever tab I started
in."

**Put a wrapper ahead of the real `herdr` binary in `PATH` that refuses
`pane close` / `tab close` / `workspace close` whenever the target ID
equals this pane's own `$HERDR_PANE_ID` / `$HERDR_TAB_ID` /
`$HERDR_WORKSPACE_ID`.** This exists because a real orchestrator instance
died this way once: a cleanup loop closing a batch of "done" tabs swept up
its own tab ID along with the rest, killing its own pane mid-loop (confirmed
in Herdr's own server log — a single `tab.close` call took down several
panes at once, immediately followed by consecutive `tab.close` calls
erroring out because the calling process's own connection was already
gone). The wrapper should be transparent for every other command; if a
self-close is ever genuinely intended, give it an explicit bypass env var.
Verify the wrapper is present and actually first in `PATH` before doing
bulk closes in any new session — a package manager update or reinstall can
silently overwrite a wrapper placed at the same path the real binary
installs to, so keep the wrapper in its own directory that no installer
will ever target.

If it's missing (fresh machine, PATH tampered with), do not proceed with any
bulk tab/pane closing until you've restored it or are manually triple-checking
every ID against `$HERDR_TAB_ID`/`$HERDR_PANE_ID` by hand.

**Recovery, if a self-closure ever happens anyway:** Claude Code sessions
persist to disk by session ID regardless of what happens to the herdr pane
that hosted them. Find the dead orchestrator's session file (it stops
updating at the moment of death, so sorting recent session files by mtime
narrows it down fast), then resume it in a fresh pane — **don't overwrite
your current live pane** — so you can inspect what it was doing before
deciding how to proceed:

```bash
herdr pane split --current --direction right --cwd "$PWD" --no-focus
herdr agent start <name> --kind claude --pane <new-pane-id> -- --resume <session-id>
```

This works: a resumed session comes back with full context intact, sitting
right where it left off.

**If the pane that resumed it ends up sharing the `orc` tab with the live
session that did the recovery** (this will usually happen, since you split
a sibling pane rather than overwriting your own), don't leave that
ambiguous — nothing auto-detects which one is "primary" and self-renames
(there is no such mechanism at all; labels only change via explicit
`herdr tab rename` / `herdr pane rename` / `herdr agent rename`). Decide
explicitly and rename both **agent handles** (distinct from the tab label,
which stays `orc` either way): the resumed session with real task
continuity becomes agent `orc`, the recovery/incident session becomes
something clearly secondary like `meta`. `herdr agent rename <target>
<name>` — target can be the live agent's current name or its pane ID.

## Workflow per unit

1. **Read the plan/roster row** for the next unit. Note what it suggests for
   vendor/model/effort — treat this as a hint, not a decision.
2. **Check real quota and real model availability before deciding.**
   - Whatever quota-tracking tool you have, check it before committing to a
     vendor for a unit of work — don't guess from memory. Swap accounts only
     when actually low, never preemptively.
   - Model names get renamed/retired. A plan written days ago may reference a
     model no longer offered. Open the target tool's own model picker and
     see what's *actually* there before committing to a name.
   - **Never select a usage-credits-backed model without asking the operator
     first** — even if credits are available and enabled. If credits are
     found *disabled*, treat that as a deliberate spend-control setting; do
     not re-enable it yourself. Ask, don't assume.
   - Pick effort/reasoning level based on the task's actual complexity, not
     just what the plan guessed — a multi-language, high-stakes, or
     "critical path" unit justifies the highest effort tier available; a
     contained single-file fix doesn't need it.
3. **Arrange panes before launching** (see Layout below).
4. **Start the agent, then IMMEDIATELY set it to auto-approve/yolo mode**
   before sending any task content (see the yolo-mode table below for
   per-tool flags — Herdr spawns the bare command name, so shell aliases
   only help in interactive shells, not here; pass the real flag directly).
   The only reason to let a sub-agent stop is if it decides on its own to
   ask for genuine human input (a real judgment call, a destructive action,
   something it's honestly unsure about) — never because of routine
   read-only tool-permission friction.
5. **Send the full task prompt** (`herdr agent prompt <name> "<prompt>"
   --wait --timeout <ms>`). Long tasks legitimately exceed the wait timeout —
   a `timeout` error from the tool just means keep checking with `herdr agent
   get`/`read`, it does not mean the agent failed.
   - **Prompts — of any length, not just large ones — can land unsubmitted,
     sitting visibly at the prompt line** (sometimes as a placeholder like
     `[Pasted text #1]`, sometimes as the literal text). This is a real,
     intermittent Herdr bug (a race between the text arriving and the Enter
     actually starting a turn) — check the project's own issue tracker for
     current status before assuming it's fixed. If `agent prompt --wait`
     comes back with `agent_prompt_stalled` (or `timeout` with
     `state_change_seq` unchanged), check `herdr agent read <name> --source
     visible` — if your text is sitting at the prompt line unsubmitted, send
     `herdr agent send-keys <name> enter` to actually submit it. This can
     recur on every single prompt in a long orchestration session — don't be
     surprised if you need this workaround repeatedly, not just once.
   - **Backticks in a double-quoted `herdr agent prompt "..."` shell string
     get expanded by your own Bash tool before Herdr ever sees them** —
     double quotes do not suppress command substitution. A prompt containing
     literal code examples like `` `some-command --version` `` gets that
     fragment actually *executed* in your own shell first, and the
     sub-agent receives whatever that command's real output happened to be,
     substituted in place of the intended literal text. Fix: single-quote
     the outer string when the prompt body contains backticks (loses `$VAR`
     expansion, which a literal prompt string rarely needs anyway), or
     escape every backtick as `` \` ``.
6. **A fresh sub-agent being skeptical of the framing is a good sign, not a
   problem.** A new session with no context of "why is a plan file telling me
   I'm Agent N of a chain" should verify the premises (read the plan file,
   check the referenced issue/PRs are real) before acting on faith. Approve
   its read-only reconnaissance and let it proceed once satisfied.
7. **New handoff/design docs commonly fail CI on markdownlint/prettier.**
   When briefing a sub-agent that will write a new `.md` file, tell it up
   front to run the repo's own markdown lint/format check on its new file
   *before* pushing, not just before declaring done — saves a full
   round-trip nearly every time. Also: a wrapped line that happens to start
   with `#NNN` (an issue reference) trips markdownlint's ATX-heading rule —
   either don't let issue references land at the start of a wrapped line, or
   backtick-wrap them.
8. **CodeRabbit review needs an explicit trigger in repos with auto_review
   disabled** — check for a `.coderabbit.yaml` with
   `reviews.auto_review.enabled: false` before assuming a PR will get
   reviewed automatically. Live-tested finding: adding a `review-ready`
   label via `gh pr edit --add-label` after the PR already exists does
   **not** reliably trigger a review — it silently stays at "skipped:
   automatic reviews are disabled." The label alone is not enough. What
   actually works: `gh pr comment <n> --repo <repo> --body "@coderabbitai
   review"` — confirmed live, flips the check to "Review in progress"
   within seconds, works regardless of the `enabled` setting. Do both (label
   for tracking, comment as the real trigger) once, at the point a
   sub-agent's PR is genuinely believed ready — not after every push, since
   the whole point of disabling auto-review is to stop paying for a fresh
   review on every incremental fixup commit.
9. **Independently verify the self-report before trusting it.** Don't just
   read the final summary. Check actual CI status (`gh pr checks`), re-read
   the real diff, and confirm concrete claims ("tests pass", "verified") from
   command output. This has caught real problems: an inaccurate "verified,
   passes" claim where CI was actually failing, and a genuine functional
   regression a cosmetic-looking fix glossed over. If verification finds a
   real problem, send the sub-agent back with the *precise* root cause (not
   just "fix your CI") — this converges much faster than a vague "something's
   wrong, look again."
10. **A unit is not done until its PR is merged (or explicitly, durably left
    open with a real documented reason).** "CI green" and "I read the diff" are
    verification steps, not a stopping point — actually run `gh pr merge`
    yourself once satisfied. Do not let a unit's row get checked off `[x]` in
    the plan file while its PR just sits open "pending review" — that phrase
    with no owner is how PRs go stale for good (see the anti-pattern below).
    The only legitimate reasons to leave a PR unmerged after verification are
    ones you'd write down: a real design decision needs the operator's input,
    or the PR is intentionally a stacked/dependent follow-up waiting on
    another PR first (name which one, in the plan file, right there).
11. **Only after the merge (or the documented exception above)**, decide the
    next unit yourself and repeat from step 1. Update the plan file's row
    yourself (check it off, note what actually happened, including any
    correction rounds) rather than trusting the sub-agent's own edit to be
    complete or accurate — spot-check it.
12. **Periodically sweep for orphaned open PRs across every repo the plan
    touches**, not just the one you're currently focused on — do this before
    starting a new phase/section of the roster, and again near the end of a
    long session. `gh pr list --repo <repo> --state open --json
    number,title,createdAt` for each repo, cross-referenced against the plan
    file's checked-off rows. A PR that's old, CI-green, and still open is a
    signal something got dropped, not a signal it's fine to ignore — go
    verify and merge it (or document why not) before moving on. This is the
    single check that catches the failure mode described in the anti-pattern
    below before it compounds across many more agents.

## Vendor quota gotchas worth knowing before routing work

If you're pacing work across multiple AI vendor accounts (Claude, Codex,
Gemini/Antigravity, OpenCode, Cursor, Copilot, Grok, etc.), a few things
that don't hold up under scrutiny even though they sound plausible:

- **Don't derive remaining quota from an assumed fixed ratio between a
  short window (e.g. 5-hour) and a long one (e.g. weekly), or from
  elapsed-time math.** This looks plausible for token-credit-metered
  vendors, but real-world reports of a single heavy task draining a large
  fraction of a week's quota in a few hours directly contradict any stable
  ratio assumption for most of them — check the live account view instead
  of extrapolating.
- **Watch for soft ceilings.** Several vendors let a headline usage limit
  silently fall through to real money once an "overage"/"use balance"
  toggle is enabled, instead of actually stopping work at the limit. Never
  select a usage-credits-backed or overage-enabled path without asking the
  operator first, even if it's technically available.
- **Never route work to a prepaid-balance account automatically.** If every
  subscription-window account is exhausted or locked out, halt and ask —
  don't fall through to spending real prepaid balance without explicit
  authorization.
- If your quota-tracking tool exposes a real pace/projection signal (e.g. a
  computed "burn" vs. "conserve" classification derived from remaining%,
  elapsed time, and learned burn rate), use that as the routing signal
  instead of hand-deriving one from raw remaining-percent — a real pace
  algorithm already accounts for things a quick mental estimate won't.

## Pane layout convention

- Never close a pane/tab. Minimize/shrink instead. The self-closure wrapper
  mentioned above refuses self-closure as a backstop, but it is not a
  reason to get sloppy about closing *other* panes/tabs either —
  minimize/shrink remains the default.
- 2 panes (you + newest agent): side by side.
- 3 panes: you = top-left quarter, newest agent = full right half, older
  agent = bottom-left quarter (under you).
- 4 panes: you stay top-left quarter, newest/current agent goes under you
  (bottom-left), the other 2 older agents share the right half.
- 5+ panes: you stay in place, current agent under you, all older agents
  stack in order on the right, shrinking as more accumulate.
- **Within the right-side stack, size by activity, not just recency**:
  agents that are `idle`/`done` get minimal space; agents still `working`
  get more room. Re-check `herdr agent get` for each right-side pane whenever
  you rearrange it and use `herdr pane resize` so active work is legible and
  finished panes are just a status strip. This can mean an older agent
  that's still working stays bigger than a more recently finished one —
  activity state wins over recency for sizing.
- **`pane resize --direction` semantics are inconsistent/counterintuitive
  across a nested split tree** — the same direction argument shrank one
  pane but no-op'd or grew a different one at another boundary, with no
  obvious rule tied to upper/lower position in the split. Don't assume a
  direction based on one earlier result. If a resize call returns
  `"changed": false` or grows the wrong pane, try the same direction/amount
  on the *other* pane sharing that boundary instead of guessing more
  directions on the same pane — that flip is what worked in practice. Treat
  this as "converge on a good-enough layout by trying a couple of calls and
  checking the resulting rect", not something to get exactly right
  analytically.
- Use `herdr pane swap --source-pane <id> --target-pane <id>` to reposition
  without closing/recreating panes when a new agent needs to become "the
  newest" in the layout.
- **Once a pane shrinks to a handful of rows (5+ agents), `agent read` may
  only return 1-2 lines even at `--lines 150`** — the terminal's actual
  rendered viewport is too small to hold much scrollback. Check
  `herdr pane get <id>` — if `viewport_rows` is small (single digits), use
  `herdr pane zoom <id> --on` to temporarily maximize it, read normally, then
  `herdr pane zoom <id> --off` to restore the layout. Don't leave it zoomed.

## Yolo-mode setup by tool (verify flags haven't moved before trusting this)

| Kind | Flag/setting |
| --- | --- |
| `claude` | `~/.claude/settings.json`: `"permissions": {"defaultMode": "bypassPermissions"}` |
| `codex` | `--dangerously-bypass-approvals-and-sandbox` |
| `cursor-agent` | `--yolo` (alias for `--force`) |
| `opencode` | `--auto` |
| `copilot` | `--allow-all` |
| `grok` | `--always-approve` |
| Google's multi-model CLI ecosystem | `--dangerously-skip-permissions` — but verify which specific binary is actually authenticated and working before assuming; some standalone single-product CLIs in this space have been deprecated in favor of a broader multi-model successor, so the flag that works can depend on which binary you're actually driving |

Shell aliases only expand in interactive shells — Herdr spawns the bare
command name directly, so pass the real flag explicitly rather than relying
on an alias defined in your shell rc file.

When a new agent kind shows up that isn't in this table, check its
`--help` output for `permission|skip|dangerous|yolo|auto|approv|sandbox`
before assuming there's no equivalent — most CLI coding agents have one.

**This is a deliberate scope trade-off, not a default to copy blindly.**
Uniform full-bypass for every sub-agent is the opposite of the
capability-narrowing pattern most multi-agent write-ups recommend (a
child's permissions should be a *subset* of the parent's, narrower for
riskier work) — it's justified here because every agent in this chain is
trusted, on the operator's own machine, working against the operator's own
accounts, and running unattended for exactly the reason full bypass
removes: routine tool-permission friction. It stops being justified the
moment a unit's task genuinely involves something higher-stakes than that
— touching production credentials/secrets, an irreversible external action
(force-push, a real financial transaction, deleting something with no
backup), or a task from a source you haven't vetted. For those, don't
blanket-yolo the pane: scope the prompt to the specific action needed and
either leave that one tool gated (so it stops for a real approval) or do
the sensitive step yourself instead of delegating it.

**Detect a genuinely stalled sub-agent, not just a slow one.** A `timeout`
from `agent prompt --wait` is expected on long tasks and is not itself a
problem (see step 5 above). It becomes one when `herdr agent get <name>`'s
`state_change_seq` hasn't moved across several consecutive checks spaced
minutes apart while the pane is still nominally `working` — that's the
"still thinking vs. actually stuck" distinction, and treating every
timeout as "just wait more" forever means a truly wedged pane never gets
noticed. If `state_change_seq` is flat for longer than the task's own
prompt would plausibly take, treat it as stalled: read the pane directly
(`herdr agent read <name> --source visible`) to see what it's actually
doing before deciding whether to nudge it, restart it, or reassign the
unit.

## Anti-patterns (things that went wrong once, don't repeat)

- Trusting a sub-agent's "CI passes" / "verified" claim without checking —
  led to shipping-adjacent PRs with a real regression that a cosmetic-looking
  fix had glossed over.
- Writing "hand off to Agent N+1 the way this handoff to you was made" into a
  sub-agent's prompt — ambiguous enough to read as "use herdr yourself,"
  which is exactly what the core rule above forbids. Say plainly: prepare
  your handoff (plan file + clipboard prompt per the existing protocol), the
  orchestrator will launch the next one.
- Re-enabling a disabled billing/credits toggle to get access to a better
  model, on the theory that "the operator said make the best call" — that
  authority covers model/vendor/effort selection, not spend-control settings.
- Assuming a model name from an older plan/roster still exists — check the
  live picker.
- **Letting a sub-agent's PR sit unmerged "pending operator review" while
  moving on to the next unit** — a real, costly failure mode. Several agents
  in a row each opened a real, CI-green PR and described it in their
  handoff as awaiting review, which read fine in isolation but had no actual
  owner for the merge step; the orchestrator kept launching new agents on
  top without circling back. A dozen PRs across multiple repos sat open for
  the rest of the session — including foundational fixes later work
  depended on — and were only discovered via a deliberate full-plan re-read
  near the end, not caught in the moment. The fix: a unit's PR gets merged
  (or the exception is explicitly written down) before you move on, full
  stop — see "Workflow per unit" steps 9-11 above. "Pending operator review"
  is not a resting state for a sub-agent's own PR when you *are* the
  orchestrator with merge authority; either you review-and-merge it now, or
  you write down specifically why not and when it'll be revisited.
- **Trusting "local check passes" without confirming it actually ran
  everything.** A sub-agent's worktree missing supporting tools/venvs makes
  its own check script *silently skip* the exact checks that matter (lint,
  format, test-collection) instead of failing — the sub-agent's "CI passes
  locally" report is then genuinely true of what ran, and still worthless.
  Before trusting a green local run, either reproduce it yourself with the
  full toolchain installed, or at minimum grep its output for
  "skip"/"not installed" next to anything load-bearing.
- **Closing your own tab/pane during a bulk cleanup loop.** An orchestrator
  instance once iterated over a list of tabs it believed were all "done"
  sub-agents and closed them one by one — its own tab ID was in that list
  (it hadn't checked its tab against `$HERDR_TAB_ID` before closing), so the
  loop killed itself mid-batch. Recovered cleanly by resuming the session by
  ID in a fresh pane (see "Orchestrator tab identity and self-closure
  defense" above), but it should never have been possible in the first
  place. Fixed with the self-closure wrapper plus the `orc` naming
  convention — both now load-bearing, don't remove either without
  replacing the protection they provide.
- **Not reading a new script's own logic just because it has passing
  tests.** A sub-agent's new notification script called a CLI subcommand
  that doesn't exist (silently a no-op) instead of the one actually
  confirmed working earlier in the same session, and separately had a
  guaranteed false-positive bug — neither one was caught by its own tests,
  because the tests were written by the same pass that missed the bugs.
  Read new orchestrator-facing code (notifications, checks, anything meant
  to fire unattended later) line by line once, independent of its test
  suite.
