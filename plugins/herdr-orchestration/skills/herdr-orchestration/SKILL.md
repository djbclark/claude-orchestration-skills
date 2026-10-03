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

## Reference files (read when needed)

- [references/quota-pacing.md](references/quota-pacing.md) — read before routing work across multiple AI vendor accounts.
- [references/pane-layout.md](references/pane-layout.md) — read before arranging, resizing, swapping or reading panes (Workflow per unit step 3).
- [references/yolo-mode-by-tool.md](references/yolo-mode-by-tool.md) — read when starting a sub-agent (Workflow per unit step 4), and when one looks stalled rather than slow.
- [references/herdr-cli-gotchas.md](references/herdr-cli-gotchas.md) — read when scripting herdr calls headlessly (new workspaces, `send-keys`, parsing output, `/exit` and resume).
- [references/anti-patterns.md](references/anti-patterns.md) — read before writing a sub-agent prompt, trusting its report, merging its PR, or bulk-closing panes.

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

## When a unit doesn't need a pane at all: ACP

Many coding-agent CLIs now speak the
[Agent Client Protocol](https://agentclientprotocol.com/) (ACP): JSON-RPC over
stdio between a client and an agent, with sessions, streamed updates, typed
tool calls, permission requests sent back to the client, and cancellation.
Some have it built in (an `acp` subcommand or `--acp` flag); others, such as
Claude Code and Codex, go through an adapter. Check each CLI's `--help` and the
protocol's agent list.

For a **one-shot, headless unit** (a review, a contained fix, a research
question) sent to an ACP-capable agent, driving it from an ACP client is
usually better than starting a Herdr pane and typing into it. A small client
built on one of the official SDKs (Python, TypeScript, Rust, Kotlin, Java;
see the protocol's Libraries pages) can:

1. send the prompt and collect the final message, with no screen scraping and
   no unsubmitted-prompt races;
2. log every tool call and permission request, plus token usage where the
   agent reports it;
3. answer permission requests itself, for example allowing edits only inside
   the unit's own files and refusing the rest. That is a per-call version of
   the capability narrowing discussed in the yolo-mode reference, with no
   bypass flag. It binds only agents that ask; some follow their own local
   permission settings and auto-allow, so pick a stricter session mode where
   the agent offers one;
4. time out cleanly by sending `session/cancel` before killing the process.

Two cautions from real runs. Always set the model explicitly: an adapter's
default can be the user's most expensive model. And a normal end of turn is
not success: one agent ended its turn cleanly with a provider error as its
whole reply. Verify the outcome as you would for a pane.

Herdr remains the right tool when the operator wants to watch or step in, when
the unit is interactive or long-lived (several prompts, in-the-moment
corrections, the session handoffs below), and for agents with no ACP mode.
ACP is the channel between the orchestrator and one agent; it does not replace
the orchestration rules in this skill.

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

0. **Before starting any unit, make sure a durable plan/roster file
   actually exists — don't assume it was created when the orchestrator
   session started.** A real gap: an orchestrator picked up several real
   units purely from conversational follow-up prompts after its initial
   bootstrap had already settled into idle, and never wrote a plan file at
   all until a supervising process noticed and asked for one explicitly.
   If your setup has any kind of restart/watchdog supervision, that
   supervision is only as good as this file — a live orchestrator with no plan file is
   unrecoverable state if it dies or gets restarted. If no plan file
   exists yet when you're about to start a unit, create one now (even a
   short one covering what's done so far and what's in flight) before
   proceeding — don't wait to be asked.
1. **Read the plan/roster row** for the next unit. Note what it suggests for
   vendor/model/effort — treat this as a hint, not a decision.
   - **"Update X" can mean more than one artifact — scope it fully before
     declaring done.** A real miss: an issue said "update the workstation,"
     but the unit as executed only bumped a CI-tracking/detection-baseline
     pin in a repo — a different thing from the actual running install the
     issue meant (a separate local checkout + daemon, still stuck on the
     old version after the PR merged). The PR-and-merge steps below (9-11)
     all looked clean because the CI-pin half genuinely was done correctly;
     nothing caught that it was only half the task until the operator asked
     directly why the old version was still showing up. Before checking a
     unit off, re-read the original issue/request's exact wording for words
     like "workstation," "install," "running," "deployed," "the actual X" —
     those point at a live artifact distinct from any repo/CI representation
     of the same version number, and both may need updating separately.
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
3. **Arrange panes before launching** (see [references/pane-layout.md](references/pane-layout.md)).
4. **Start the agent, then IMMEDIATELY set it to auto-approve/yolo mode**
   before sending any task content (see the yolo-mode table in [references/yolo-mode-by-tool.md](references/yolo-mode-by-tool.md) for
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
    with no owner is how PRs go stale for good (see [references/anti-patterns.md](references/anti-patterns.md)).
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
    in [references/anti-patterns.md](references/anti-patterns.md) before it compounds across many more agents.
