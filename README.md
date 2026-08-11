# ROCm DevOps Skills

AI-assisted skills and commands for ROCm DevOps workflows. Clone this repo and plug into **Cursor** or **Claude CLI** for automated CI triage, issue tracking, and team reporting.

## Available Skills

| Skill | File | Command | Use it when |
|-------|------|---------|-------------|
| **Monorepo Gardener** | [`gardener/monorepo_gardener_skill.md`](gardener/monorepo_gardener_skill.md) | `/gr` | You are on the **rocm-libraries / rocm-systems** gardener rotation and someone says "my PR is blocked" or asks for a bypass |
| **Bump PR Gardener** | [`gardener/bumppr_skill.md`](gardener/bumppr_skill.md) | `/tr` | You are triaging the twice-daily **bot bump PRs** in ROCm/TheRock |

Both cover the same rotation from different ends: `/gr` is per-request triage on human PRs and
post-submit reds, `/tr` is the scheduled bump-PR sweep. The normative policy for the role lives in
each repo's own doc and wins over anything here —
[rocm-libraries](https://github.com/ROCm/rocm-libraries/blob/develop/docs/gardening.md),
[rocm-systems](https://github.com/ROCm/rocm-systems/blob/develop/docs/gardening.md),
[RFC0002](https://github.com/ROCm/TheRock/blob/main/docs/rfcs/RFC0002-MonoRepo-Gardener-Rotations.md).
These skill files are the executable layer: the exact `gh` recipes, the traps that produce wrong
verdicts, and the shape of the artifacts you hand back.

## Quick Start

### Prerequisites

- [GitHub CLI (`gh`)](https://cli.github.com/) — authenticated with access to `ROCm/TheRock`,
  `ROCm/rocm-libraries` and `ROCm/rocm-systems`. `read:org` scope is enough for everything in these
  skills, including listing team members
- [ripgrep (`rg`)](https://github.com/BurntSushi/ripgrep) — for fast log searching
- `python3` — a few of the recipes pipe JSON through it
- Either **Cursor IDE** or **Claude CLI** (or both)

```bash
git clone https://github.com/AmosLewis/rocm-devops-skills.git
cd rocm-devops-skills
```

### Weekly Handoff (every Tuesday)

When you take over gardener rotation, gather previous context **before** triaging.

**Monorepo gardener (`/gr`)** — three things, in this order:

1. **Enumerate the required checks yourself**, for every repo you now cover. The sets differ between
   `rocm-libraries` and `rocm-systems`, and the two `gardening.md` files differ by only about six
   lines, which makes them easy to conflate.

   ```bash
   gh api repos/ROCm/rocm-libraries/rulesets --jq '.[] | "\(.id) \(.name) \(.target)"'
   gh api repos/ROCm/rocm-libraries/rulesets/<ID> \
     --jq '[.rules[] | select(.type=="required_status_checks")
            | .parameters.required_status_checks[].context]'
   ```

2. **Inherit the known-issue baseline** from the previous gardener's tracker and the open
   [gardener-labelled issues](https://github.com/ROCm/rocm-libraries/issues?q=is%3Aissue+state%3Aopen+label%3Agardener).
   Remember that ROCm/TheRock issues frequently carry **no labels at all**, so always search by error
   text across all three repos rather than by label.
3. **Read the rotation table** on the internal Confluence page for the current gardener list, and note
   who owns the SRE rotation this week — the fleet is theirs, the per-PR verdict is yours.

**Bump PR gardener (`/tr`)** — two sources:

1. **Teams**: Go to the **Gardening-Bump-PR** channel, copy the last `Bump PR Tracker` message from the previous gardener. Save it as your reference for known issues.
2. **Confluence**: Check the master issue tracking page — [Bump Failure Tracking by Component and Owner](https://amd.atlassian.net/wiki/spaces/MLSE/pages/1621581386/Bump+Failure+Tracking+by+Component+and+Owner). Cross-reference with Teams to see which issues are resolved vs still open.

### Optional: Atlassian MCP Plugin (Confluence access from AI)

If you want the AI agent to directly query the Confluence tracking page, set up the [Atlassian MCP server](https://www.npmjs.com/package/@anthropic/atlassian-mcp-server):

**For Cursor** — add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "atlassian": {
      "command": "npx",
      "args": ["-y", "@anthropic/atlassian-mcp-server"],
      "env": {
        "ATLASSIAN_SITE_URL": "https://amd.atlassian.net",
        "ATLASSIAN_USER_EMAIL": "<your-email>",
        "ATLASSIAN_API_TOKEN": "<your-token>"
      }
    }
  }
}
```

**For Claude CLI** — add to `~/.claude/mcp.json` with the same config.

Generate your Atlassian API token at: https://id.atlassian.com/manage-profile/security/api-tokens

Once configured, the AI can directly read and update the Confluence tracking page during triage.

---

## Usage: Cursor IDE

### Option A: Custom commands (`/gr`, `/tr`)

1. Copy the command files into your Cursor workspace:

```bash
mkdir -p <your-project>/.cursor/commands
cp gardener/commands/gr.md <your-project>/.cursor/commands/gr.md   # monorepo gardener
cp gardener/commands/tr.md <your-project>/.cursor/commands/tr.md   # bump PR triage
```

2. Copy the skill files somewhere Cursor can reference them:

```bash
mkdir -p <your-project>/skills/gardener
cp gardener/monorepo_gardener_skill.md <your-project>/skills/gardener/
cp gardener/bumppr_skill.md            <your-project>/skills/gardener/
```

3. Update the `Context:` line in each command to point at your skill path:

```markdown
Context: @skills/gardener/monorepo_gardener_skill.md
```

4. In Cursor chat, type:

```
/gr https://github.com/ROCm/rocm-libraries/pull/10250
Reporter: "3 checks failing, all look like infra. Can you merge today? BKC cut-off."
```

Cursor reads the skill, enumerates the required checks, reads the merge state, classifies each red,
and produces:
- `MMDD-pr<PR>-respond.md` — the reply in its fixed three-part shape, ready to paste
- `MMDD-pr<PR>-<topic>.md` — the triage note behind it (evidence, timings, log excerpts)
- one new row in `tracker.md`

Or, for the bot bump PRs:

```
/tr https://github.com/ROCm/TheRock/pull/4839 https://github.com/ROCm/TheRock/pull/4840
```

### Option B: Cursor Rules (always-on context)

Add to `.cursor/rules/gardener.mdc`:

```
---
description: "Gardener triage workflows"
globs: ["**/triage/**", "**/gardener/**"]
alwaysApply: false
---

@skills/gardener/monorepo_gardener_skill.md
@skills/gardener/bumppr_skill.md
```

Then the skills are automatically loaded when you work in triage files.

---

## Usage: Claude CLI

Pick the skill file for the job — `gardener/monorepo_gardener_skill.md` for a blocked PR or bypass
request, `gardener/bumppr_skill.md` for the bot bump PRs.

### Option A: Pipe the skill as system prompt

```bash
cat gardener/monorepo_gardener_skill.md | claude --system-prompt - \
  "PR blocked, reporter asks for a bypass: https://github.com/ROCm/rocm-libraries/pull/10250"
```

### Option B: Use as a CLAUDE.md project instruction

1. Copy the skill into your working directory:

```bash
cp gardener/monorepo_gardener_skill.md ./CLAUDE.md
```

2. Run Claude CLI in that directory:

```bash
claude "Triage https://github.com/ROCm/rocm-libraries/pull/10250 — reporter wants a bypass today"
```

Claude will automatically read `CLAUDE.md` as project context.

### Option C: Direct prompt with file reference

```bash
claude --file gardener/bumppr_skill.md \
  "Triage these bump PRs: https://github.com/ROCm/TheRock/pull/4839"
```

### Shell aliases

```bash
# Add to ~/.bashrc or ~/.zshrc
alias gr='claude --file ~/rocm-devops-skills/gardener/monorepo_gardener_skill.md'
alias tr-bump='claude --file ~/rocm-devops-skills/gardener/bumppr_skill.md'

# Usage:
gr "PR blocked, reporter asks for a bypass: https://github.com/ROCm/rocm-libraries/pull/10250"
tr-bump "Triage: https://github.com/ROCm/TheRock/pull/4839 https://github.com/ROCm/TheRock/pull/4840"
```

---

## What the triage produces

**Monorepo gardener (`/gr`)** — three artifacts, deliberately separate so the tracker stays scannable:

| Output | Format | Purpose |
|--------|--------|---------|
| `MMDD-pr<PR>-respond.md` | Conclusion sentence + `Red check \| Keypoint` table + one gap sentence, with the long form under `# Optional detail` | Paste into the PR thread or Teams as-is |
| `MMDD-pr<PR>-<topic>.md` | Evidence, timestamps, log excerpts, the "why not just wait" argument | Quote only if someone pushes back |
| `tracker.md` | One table row per PR, edited in place | Handoff and decision log |

**Bump PR gardener (`/tr`)**:

| Output | Format | Purpose |
|--------|--------|---------|
| `<r-l>-<r-s>.md` | Markdown table with Run/Job/Issue links | Copy into GitHub PR comments |
| `<r-l>-<r-s>-teams.md` | Bullet list with issue links | Copy into Teams Gardening-Bump-PR channel |
| `<PR>/<MMDD>-...-ci-issue.md` | GitHub issue template | Copy into GitHub "New Issue" (only for NEW failures) |

## Examples

- [`gardener/examples/pr10250-bypass/`](gardener/examples/pr10250-bypass/) — a real bypass request on
  `rocm-libraries` (Aug 10, 2026): the reply as sent, the detail held in reserve, and the tracker row
  it produced. Shows why a re-run could not clear the reds and how the coverage gap was stated rather
  than papered over.
- [`gardener/examples/week17-0427/`](gardener/examples/week17-0427/) — a real bump PR triage
  (Apr 27, 2026) with all 9 failed jobs mapped to existing issues, plus the Teams message.

---

## Repo Structure

```
rocm-devops-skills/
├── README.md                          # this file
├── gardener/                          # gardener rotation skills
│   ├── monorepo_gardener_skill.md     # rocm-libraries / rocm-systems PR + post-submit triage
│   ├── bumppr_skill.md                # TheRock bump PR triage
│   ├── commands/
│   │   ├── gr.md                      # Cursor /gr command definition
│   │   └── tr.md                      # Cursor /tr command definition
│   └── examples/
│       ├── pr10250-bypass/            # real bypass case
│       │   ├── README.md
│       │   ├── pr10250-respond.md
│       │   └── tracker-row.md
│       └── week17-0427/               # real bump PR triage
│           ├── 4839-4840.md
│           └── 4839-4840-teams.md
└── <future-skills>/                   # other DevOps skills go here
```

## Contributing

When adding a new skill:
1. Create a folder under the root (e.g. `ci-monitoring/`, `release-mgmt/`), or add to an existing one
   if it serves the same role
2. Include a `<name>_skill.md` with the full workflow
3. Include a `commands/` subfolder with any Cursor command `.md` files
4. Include `examples/` with real-world output
5. Update this README's "Available Skills" table

Content rules, since this repo is public:

- No internal hostnames, credentials, or dashboard URLs. Use a placeholder and point at the internal
  Confluence page instead — the internal Math CI host in `monorepo_gardener_skill.md` is the pattern
  to follow.
- No rosters mapping colleagues' real names to GitHub logins. Publish the *method* for finding the
  right reviewer, not the answer.
- Every claim about a gate, ruleset or required check should come with the command that verifies it,
  because these change and a stale table is worse than no table.
