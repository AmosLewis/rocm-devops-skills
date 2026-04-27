# ROCm DevOps Skills

AI-assisted skills and commands for ROCm DevOps workflows. Clone this repo and plug into **Cursor** or **Claude CLI** for automated CI triage, issue tracking, and team reporting.

## Available Skills

| Skill | Folder | Description |
|-------|--------|-------------|
| **Bump PR Gardener** | `gardener/` | Triage TheRock bump PR CI failures, compare with known issues, generate GitHub-ready trackers and Teams messages |

## Quick Start

### Prerequisites

- [GitHub CLI (`gh`)](https://cli.github.com/) — authenticated with access to `ROCm/TheRock`
- [ripgrep (`rg`)](https://github.com/BurntSushi/ripgrep) — for fast log searching
- Either **Cursor IDE** or **Claude CLI** (or both)

```bash
git clone https://github.com/AmosLewis/rocm-devops-skills.git
cd rocm-devops-skills
```

### Weekly Handoff (every Tuesday)

When you take over gardener rotation, gather previous context **before** triaging:

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

### Option A: Custom command (`/tr`)

1. Copy the command file into your Cursor workspace:

```bash
mkdir -p <your-project>/.cursor/commands
cp gardener/commands/tr.md <your-project>/.cursor/commands/tr.md
```

2. Copy the skill file somewhere Cursor can reference it:

```bash
cp gardener/bumppr_skill.md <your-project>/skills/gardener/bumppr_skill.md
```

3. Update the `Context:` line in `tr.md` to point to your skill path:

```markdown
Context: @skills/gardener/bumppr_skill.md
```

4. In Cursor chat, type:

```
/tr https://github.com/ROCm/TheRock/pull/4839 https://github.com/ROCm/TheRock/pull/4840
```

Cursor will read the skill, auto-discover failed jobs, fetch logs, triage, and produce:
- `<r-l PR>-<r-s PR>.md` — GitHub-comment-ready tracker
- `<r-l PR>-<r-s PR>-teams.md` — Teams copy-paste message
- Issue drafts for any genuinely NEW failures

### Option B: Cursor Rules (always-on context)

Add to `.cursor/rules/gardener.mdc`:

```
---
description: "Bump PR gardener triage workflow"
globs: ["**/triage/**", "**/gardener/**"]
alwaysApply: false
---

@skills/gardener/bumppr_skill.md
```

Then the skill is automatically loaded when you work in triage files.

---

## Usage: Claude CLI

### Option A: Pipe the skill as system prompt

```bash
cat gardener/bumppr_skill.md | claude --system-prompt - \
  "Triage these bump PRs: https://github.com/ROCm/TheRock/pull/4839 https://github.com/ROCm/TheRock/pull/4840"
```

### Option B: Use as a CLAUDE.md project instruction

1. Copy the skill into your working directory:

```bash
cp gardener/bumppr_skill.md ./CLAUDE.md
```

2. Run Claude CLI in that directory:

```bash
claude "Triage bump PRs: https://github.com/ROCm/TheRock/pull/4839 https://github.com/ROCm/TheRock/pull/4840"
```

Claude will automatically read `CLAUDE.md` as project context.

### Option C: Direct prompt with file reference

```bash
claude --file gardener/bumppr_skill.md \
  "Triage these bump PRs: https://github.com/ROCm/TheRock/pull/4839"
```

### Claude CLI with the /tr command pattern

Create a shell alias for convenience:

```bash
# Add to ~/.bashrc or ~/.zshrc
alias tr-bump='claude --file ~/rocm-devops-skills/gardener/bumppr_skill.md'

# Usage:
tr-bump "Triage: https://github.com/ROCm/TheRock/pull/4839 https://github.com/ROCm/TheRock/pull/4840"
```

---

## What the triage produces

| Output | Format | Purpose |
|--------|--------|---------|
| `<r-l>-<r-s>.md` | Markdown table with Run/Job/Issue links | Copy into GitHub PR comments |
| `<r-l>-<r-s>-teams.md` | Bullet list with issue links | Copy into Teams Gardening-Bump-PR channel |
| `<PR>/<MMDD>-...-ci-issue.md` | GitHub issue template | Copy into GitHub "New Issue" (only for NEW failures) |

## Examples

See `gardener/examples/week17-0427/` for a real triage from Apr 27, 2026:
- `4839-4840.md` — tracker with all 9 failed jobs mapped to existing issues
- `4839-4840-teams.md` — Teams message sent to Gardening-Bump-PR channel

---

## Repo Structure

```
rocm-devops-skills/
├── README.md                          # this file
├── gardener/                          # Bump PR gardener skills
│   ├── bumppr_skill.md                # main skill (triage workflow)
│   ├── commands/
│   │   └── tr.md                      # Cursor /tr command definition
│   └── examples/
│       └── week17-0427/               # real triage example
│           ├── 4839-4840.md
│           └── 4839-4840-teams.md
└── <future-skills>/                   # other DevOps skills go here
```

## Contributing

When adding a new skill:
1. Create a folder under the root (e.g. `ci-monitoring/`, `release-mgmt/`)
2. Include a `<name>_skill.md` with the full workflow
3. Include a `commands/` subfolder with any Cursor command `.md` files
4. Include `examples/` with real-world output
5. Update this README's "Available Skills" table
