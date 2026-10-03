# Yolo-mode setup by tool (verify flags haven't moved before trusting this)

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

**For a one-shot unit, ACP offers the narrower option without a bypass
flag.** Over the Agent Client Protocol the agent sends permission requests to
the client, so an ACP client can allow edits only under the unit's own paths,
or refuse every edit for a read-only review. This only binds agents that ask;
others apply their own local settings. The flags above are for interactive
panes. See SKILL.md, "When a unit doesn't need a pane at all: ACP".

**Detect a genuinely stalled sub-agent, not just a slow one.** A `timeout`
from `agent prompt --wait` is expected on long tasks and is not itself a
problem (see ["Workflow per unit"](../SKILL.md#workflow-per-unit) step 5). It becomes one when `herdr agent get <name>`'s
`state_change_seq` hasn't moved across several consecutive checks spaced
minutes apart while the pane is still nominally `working` — that's the
"still thinking vs. actually stuck" distinction, and treating every
timeout as "just wait more" forever means a truly wedged pane never gets
noticed. If `state_change_seq` is flat for longer than the task's own
prompt would plausibly take, treat it as stalled: read the pane directly
(`herdr agent read <name> --source visible`) to see what it's actually
doing before deciding whether to nudge it, restart it, or reassign the
unit.
