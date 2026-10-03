---
name: steps
description: >-
  Step the user through the open items one at a time, each as its own arrow-key
  multiple-choice prompt (AskUserQuestion) with the recommended option first,
  acting on each answer before asking the next. Use when the user types /steps
  (optionally with item numbers or a topic), says "step me through it", "one at
  a time", or "walk me through" a list of open items, options or pending
  decisions.
---

# steps — one open item at a time, recommendation first

The user is choosing, not reading. Give them one decision per prompt, already
ranked, and do what they picked before asking the next one. A prose list of
options makes them write a reply that enumerates what they want. A prompt lets
them pick with the arrow keys.

Ask **one question per call**, not a batch, so each answer can change the next
question.

## 1. Collect the items

1. **From the arguments.** Numbers (`/steps 2 4`, `/steps 1a 3`) refer to items in
   your most recent numbered reply. A topic (`/steps the backup stuff`) means the
   open items about that topic.
2. **Otherwise from the conversation.** Take every open item from the latest
   list: loose ends, options you offered, deferred work, questions you asked that
   were never answered.
3. **Drop anything already decided.** Don't re-litigate it.
4. **Never invent items to fill the walk.** If nothing is open, say so in one
   line.

Before the first prompt, show the queue as a short numbered list of titles
("4 items: 1. …"), so the user knows how long this will take.

## 2. Ask one item per prompt

Make each item a single `AskUserQuestion` call with exactly one question:

1. Put the position in the `header` chip, `2/4`. Put the item and enough context
   to decide it in the question: the finding, the number, the risk. Keep it to a
   sentence or two. Anything longer belongs in a short prose line just before the
   call.
2. Put your **recommended option first**, labelled `(Recommended)`, and say why
   in its description.
3. Give 2–4 options that lead to genuinely different outcomes, and put each
   option's consequence in its description. Include "Leave it as is" or "Skip for
   now" wherever that is a real choice. "Other" is added automatically, and the
   user can type `stop` there to end the walk.
4. Use `preview` when the user would be comparing concrete artifacts: a diff, a
   config snippet, command output.

## 3. Act, then move on

1. **Do what they picked before you ask the next question**, if it is small and
   inside the session's scope. Confirm it in one line ("Done: pushed `abc123`"),
   then ask the next one.
2. **Queue anything bigger** (a long build, a multi-file change, a sub-agent
   dispatch). Say it is queued and do the queue right after the last item.
3. **If an answer or its result changes a later item**, re-rank that item's
   options or drop it, and say so in a line. Don't ask a question an earlier
   answer has already settled.
4. On `stop`, stop. Report what was decided and what is still open.

## 4. Close with a summary

End with a table: item, choice, outcome (done / queued / skipped / left open).
Number any remaining open items so the user can run `/steps` on them again.

## What this is not

1. Not an audit. The `loose` skill finds the loose ends and verifies each one;
   `steps` walks a list that already exists, wherever it came from. They compose:
   run `loose` to find what is open, and `steps` to decide it.
2. Not a licence to widen scope. An option you recommend should close the item,
   not start new work the user didn't ask for.
