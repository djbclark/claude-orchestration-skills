---
name: handoff
description: Create a deep Tier 2 handoff document — chain-tagged, DAG-linked, mined from the full conversation — in your durable notes/memory location. Use when pausing substantial work, before ending a long session, or when the operator says "do a handoff", "create a handoff", "save session context".
---

# Handoff — Tier 2 deep recovery document

The deeper companion to the `session-handoff` (Tier 1) skill in this
same plugin. Tier 1 is a cheap pointer; Tier 2 is an immutable,
chain-tagged recovery document with a DAG of parent/child links,
committed somewhere durable — written when work is substantial enough
that losing the conversational nuance (failed approaches, rejected
alternatives, raw measurements) would actually cost real re-derivation
time.

**Where Tier 2 docs live is a decision you make for your own setup, not
prescribed here.** The reference implementation this plugin was built
from commits them directly to a private "memory" repo's master branch
under a narrow, explicitly-scoped exception to that repo's normal
branch/PR flow — because durable agent operational state can't wait on
a release cadence, and a Tier 2 doc that only lands once its originating
branch merges (or never, if the branch is abandoned) defeats the
point. If you adopt a similar committed-memory-repo pattern, replace
Step 6 below with your own equivalent commit flow; if you don't have
one yet, the minimum viable version is "a directory that's actually
backed up and versioned, written to immediately, not batched."

## Guards

- Only the workspace-owning session runs this. Sub-agents never do.
- Never generate handoff-like documents freeform outside this skill.
- Only when the operator (or owning orchestrator) explicitly wants a
  handoff created now. If ambiguous, ask.
- Not in plan mode.

## Step 1 — Gather external state (parallel shell commands, never agents)

`git log --oneline -15`, `git diff --stat`, `git status -s | head -30`,
`git branch --show-current`, `git rev-parse HEAD`; any issue-tracker
state relevant to the current work (adapt to whatever tracker, if any,
this workspace uses); list existing handoffs for this repo in your
notes location so you can check for a parent.

## Step 2 — Chain tag and lineage

Chain tag, first match: (1) an epic/parent issue ID from your tracker;
(2) 1–4 individual issue IDs (list); (3) `standalone-{4-hex}`
(`python3 -c "import secrets;print(secrets.token_hex(2))"`).

Lineage is an explicit DAG:
- `handoff_id`: fresh 4-hex id.
- `parent_handoff_ids`: if this session started from a resume prompt
  naming a parent handoff file, that file's id (deterministic —
  primary). Else, search your notes location for the chain tag as
  RECOVERY ONLY: a shared tracker ID is a candidate, not proof — read
  the candidate's "Where We're Going"; only clear continuation makes it
  a parent, and the new doc must say `lineage: inferred`. Doubt → ask
  the operator. No parent → `[]`.

## Step 3 — Mine the conversation

Announce pass choice: Quick (<100K context) / Deep (100K–500K) /
Chunked map-reduce (500K+). Extract, in chronological order where it
matters: goals; work completed (files, functions, specifics); approaches
tried; FAILED approaches + why (most expensive to rediscover — never
skip); test results with raw numbers; data files created; decisions +
rejected alternatives; discoveries/gotchas; code analysis (signatures,
constants); operator preferences expressed; open questions; dependencies.

## Step 4 — Write the file

Path (adapt the root to your own notes location):
`<notes-root>/handoffs/<repo>/HANDOFF_{chain}_{slug}_{YYYY-MM-DD}_{handoff_id}.md`
(slug: 2–4 kebab words; multi-issue chains use the primary issue in the
filename). Create the repo subdirectory if needed.

    ---
    schema_version: 1
    handoff_id: <4 hex>
    parent_handoff_ids: []
    lineage: deterministic|inferred|none
    chain: [<ids>]
    repo: <target repo>
    workspace: <task dir name>
    branch: <branch>
    head_sha: <sha>
    created_at: <ISO 8601 with offset>
    writer: claude-code
    ---
    # Handoff — <title>
    ## The Goal
    ## Where We Are
    ## What We Tried            <- failed approaches, chronological, with why
    ## Key Decisions            <- chosen AND rejected
    ## Evidence & Data          <- real numbers, file paths
    ## Operator Feedback
    ## Where We're Going        <- ordered; item 1 is THE next action
    ## Quick Start              <- exact commands for the next session

## Step 5 — Validation gate (all required; line count is NOT the gate)

- [ ] Objective stated
- [ ] Exact git state (branch, head_sha, dirty list)
- [ ] Files changed this session
- [ ] Tests run + results (or explicit "none run")
- [ ] Decisions + rejected alternatives
- [ ] Failed approaches + why
- [ ] Blockers / open questions
- [ ] ONE explicit next action at the top of Where We're Going
- [ ] Parent linkage (ids, or explicit none)
- [ ] Redaction: no credentials, tokens, `.env` values, key material,
      anywhere in the doc

Any unchecked box: fix before proceeding. Thin sections: expand from the
conversation, don't pad.

## Step 6 — Commit

Use your own durable-notes commit flow here (see the note at the top of
this skill). Whatever it is, the shape that works: fetch/sync first so
you're not diverging from a remote that moved; a commit that touches
*only* the new handoff file (never bundled with unrelated changes); push
immediately, don't batch — the whole point of Tier 2 is that it survives
even if the session that wrote it never comes back.

## Step 7 — Update Tier 1

Via the `session-handoff` skill's writer protocol: set `latest_handoff`
to the new handoff doc's path, refresh Current State, add a history
entry. Then report to the operator: file path, chain + lineage,
validation outcome, the next action.
