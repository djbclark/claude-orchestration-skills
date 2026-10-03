---
name: loose
description: >-
  Audit the current session for loose ends — unfinished work, unverified claims,
  leftover test artifacts, findings that exist only in chat, undisclosed
  deviations, unreported upstream bugs — then prompt the user to decide each one
  as selectable multiple choice. Use when the user types /loose, asks "any loose
  ends?", "anything outstanding?", "did we finish everything?", or asks to be
  walked through what is left. Also use unprompted before a handoff or at the end
  of a long working session.
---

# loose — find what is unfinished, then make it decidable

Two halves, and the second is not optional. **Audit by verification, then prompt
the user to choose.** A prose list of what you remember is the failure mode this
skill exists to replace.

## Rule 1 — verify, never recall

Your memory of the session is the *input* to the audit, not the audit itself.
Every item gets a command behind it before it reaches the user.

This matters more than it sounds. In the session this skill was written from,
auditing properly instead of from memory found a gap nobody had noticed — an
always-loaded instruction file whose summary never mentioned the rule the entire
session had just established, so the work was one click away and unadvertised. It
also confirmed two things that had merely been *assumed*, and refuted one claim
that had already been stated to the user as fact.

Corollary: when a check contradicts something you said earlier, **say so plainly
in the audit**. An audit that quietly preserves your earlier framing is worthless.

## Rule 2 — the sweep

Work the list. Each line is a command, not a memory.

1. **Repo state, every repo touched.** `git status --porcelain` and
   `git status -sb` per repo: dirty files, unpushed commits, detached heads. In a
   checkout shared with other sessions or agents you often cannot attribute a
   change by `git log --author`, so if you did not touch it, label it "not mine"
   and leave it alone.
2. **Test and probe artifacts.** Everything you created to prove something:
   throwaway config entries, marker functions appended to source, backup files,
   scratch clones, caches you deleted or rebuilt. Grep for your own probe names.
   A marker function left behind in a tracked file is the worst kind of leftover.
3. **Background work.** Tasks still running; agents idle with output you never
   collected. An agent that looks finished with nothing delivered means *not yet
   delivered* — re-task it to write its report to a file. Never reconstruct what
   it would have said; a plausible invention is indistinguishable from a finding
   once it is in your reply.
4. **Claims you made but did not verify.** Scan your own replies for assertions
   stated flatly. Anything inferred rather than observed either gets checked now
   or gets downgraded to "assumed" in the audit.
5. **Findings that exist only in chat.** A measurement, a defect, a workaround, a
   decision and its reasoning — if it is not in a repo, a doc, or a memory file,
   it dies at session end. Make it durable *before* reporting it as a loose end.
6. **Docs that reality has overtaken.** Did this session falsify a standing note,
   an always-loaded instruction, or a pointer? Check the files that **load every
   session** specifically: a rule nobody reads is not a rule. Stale instructions
   are worse than missing ones, because they are followed.
7. **Upstream bugs found and not reported.** Any third-party defect you hit with a
   clean reproduction. **Search existing issues *and* pull requests first** —
   open and closed, several search terms. The existing thread often explains the
   behaviour, or hands you the fix outright, and a duplicate costs a maintainer
   real time.
8. **Deviations from the user's decisions.** Anything you did that cut against a
   choice they had already made, even reversibly. Disclose it in the audit if you
   have not already. Surfacing it later, in a summary, is the actual failure.
9. **Deferred by them, not by you.** List these so they are not mistaken for
   oversights — and do not re-litigate them.
10. **Verified-closed items.** One line, so the same questions do not come back
    next session.

## Rule 3 — then prompt, do not prose

Hand every live decision back with **`AskUserQuestion`**: one decision per
question, the recommended option first and labelled `(Recommended)`, up to four
per call, continuing in further calls until the tail is covered. Include a genuine
"leave it as is" option wherever that is a real choice, and spell out the
consequence in each option's description.

Prose is for the context they need to choose *with* — the numbers, the risk, what
you found. Not for the choosing itself. The difference is whether they have to
compose a reply enumerating what they want, or can just pick.

Categories 9 and 10 are **not** questions. Report them in a line each and move on.

## What this is not

- **Not a handoff.** Use a session-handoff skill to persist context so work can
  resume. This is about deciding what is still owed.
- **Not task verification.** A verify-style skill proves one task meets its
  acceptance conditions. This sweeps a whole session, including the things nobody
  set acceptance conditions for.
- **Not a licence to fix.** Finding a loose end does not authorise acting on it.
  The one exception is category 5: make a finding durable before reporting it,
  because reporting a finding whose record dies with the session achieves nothing.

## Related tools

If you want session-close to also *ship*, [conclude-it](https://github.com/DevOtts/conclude-it)
is more comprehensive — a ship pipeline (test gate → deploy → prod gate) plus a
close core of debrief, ledger, sweep and verdict, with per-repo configuration.
This skill deliberately stays out of deploy and keeps the decision-prompting half,
which session-close tools generally do not do.
