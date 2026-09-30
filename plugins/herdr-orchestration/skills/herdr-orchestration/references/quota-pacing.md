# Vendor quota gotchas worth knowing before routing work

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
