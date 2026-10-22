# ROCm DevOps Skills

Agent skills for ROCm DevOps. Each skill is one folder an agent can discover on its own. Cursor commands under [`.cursor/commands/`](.cursor/commands/) are optional shortcuts.

The layout matches the [Agent Skills](https://github.com/amd/skills) format used by [amd/skills](https://github.com/amd/skills) and [TheRock skills](https://github.com/ROCm/TheRock/tree/main/skills): `skills/<name>/SKILL.md`, with `name` equal to the directory name.

## Catalog

| Skill | Command | Use it when |
| --- | --- | --- |
| [monorepo-gardener-triage](skills/monorepo-gardener-triage/SKILL.md) | `/gr` | A human PR on **rocm-libraries** or **rocm-systems** is blocked, or someone asks for a bypass. Classify. Do not execute the merge. |
| [therock-bump-pr-triage](skills/therock-bump-pr-triage/SKILL.md) | `/tr` | The twice-daily **bot bump PRs** in ROCm/TheRock. |
| [gardener-rotation-handover](skills/gardener-rotation-handover/SKILL.md) | `/ho` | Last day of the gardener week. Post-merge sweep, handover doc, Teams message. |
| [teams-gardener-requests](skills/teams-gardener-requests/SKILL.md) | `/tgr` | Pull merge / override / help asks from the gardening Teams channels. Read-only. |
| [process-merge-override](skills/process-merge-override/SKILL.md) | `/pmo` | Execute an override after triage says the required-gate reds are known infra. |

`/gr` classifies. `/pmo` merges. `/tgr` only lists the asks. `/tr` is the bump-PR sweep. `/ho` closes the week.

Policy in each repo wins over these skills:
[rocm-libraries gardening](https://github.com/ROCm/rocm-libraries/blob/develop/docs/gardening.md),
[rocm-systems gardening](https://github.com/ROCm/rocm-systems/blob/develop/docs/gardening.md),
[RFC0002](https://github.com/ROCm/TheRock/blob/main/docs/rfcs/RFC0002-MonoRepo-Gardener-Rotations.md).

`monorepo-gardener-triage` keeps the per-request path in `SKILL.md` and the long proofs in [`reference.md`](skills/monorepo-gardener-triage/reference.md), so the skill file stays within the 500-line body limit used by amd/skills.

## Install

This repo is not in the amd/skills catalog, so `npx skills add amd/skills` does not install it.

The same `SKILL.md` works in Cursor, Claude Code, and Codex. There is no per-agent copy.

### As a plugin

The repo ships plugin manifests in the same shape as amd/skills: [`.claude-plugin/`](.claude-plugin/marketplace.json), [`.cursor-plugin/`](.cursor-plugin/marketplace.json), [`.codex-plugin/`](.codex-plugin/plugin.json), and [`.agents/plugins/`](.agents/plugins/marketplace.json). In Claude Code:

```text
/plugin marketplace add AmosLewis/rocm-devops-skills
```

The plugin bundles the three triage and handover skills only. `teams-gardener-requests` needs a Teams token or a signed-in Chrome, and `process-merge-override` runs admin merges, so install those two by hand when you need them.

### By hand

Clone, then copy or symlink the skill folders you want:

```bash
git clone https://github.com/AmosLewis/rocm-devops-skills.git
cd rocm-devops-skills
```

| Agent | Skills directory |
| --- | --- |
| Cursor | `~/.cursor/skills/` or `<project>/.cursor/skills/` |
| Claude Code | `~/.claude/skills/` or `<project>/.claude/skills/` |
| Codex | `$HOME/.agents/skills` or `<repo>/.agents/skills` |

```bash
ln -s "$PWD/skills/monorepo-gardener-triage" ~/.cursor/skills/monorepo-gardener-triage
```

Open this repo as the Cursor workspace and the commands in `.cursor/commands/` (`/gr`, `/tr`, `/ho`, `/tgr`, `/pmo`) are available without copying. Each command tells the agent which `SKILL.md` to read.

### Prerequisites

- [GitHub CLI (`gh`)](https://cli.github.com/), with access to `ROCm/TheRock`, `ROCm/rocm-libraries`, and `ROCm/rocm-systems`. `read:org` is enough to list team members.
- [ripgrep (`rg`)](https://github.com/BurntSushi/ripgrep)
- `python3`

`teams-gardener-requests` and the stacked path in `process-merge-override` also need the Teams token or a signed-in Chrome remote-debugging port. Those skills state the exact prerequisite.

### Taking the rotation

1. Enumerate required checks per repo. The two `gardening.md` files are easy to mix up.

   ```bash
   gh api repos/ROCm/rocm-libraries/rulesets --jq '.[] | "\(.id) \(.name) \(.target)"'
   gh api repos/ROCm/rocm-libraries/rulesets/<ID> \
     --jq '[.rules[] | select(.type=="required_status_checks")
            | .parameters.required_status_checks[].context]'
   ```

2. Inherit the known-issue baseline from the previous handover and from open issues. Search by error text. TheRock issues often have no labels.
3. For bump PRs, start from the last Teams **Gardening-Bump-PR** tracker and the [Bump Failure Tracking](https://amd.atlassian.net/wiki/spaces/MLSE/pages/1621581386/Bump+Failure+Tracking+by+Component+and+Owner) page.

## Examples

- [pr10250 bypass](skills/monorepo-gardener-triage/examples/pr10250-bypass/) — reply shape, held-back detail, tracker row.
- [week 32 handover](skills/gardener-rotation-handover/examples/week32-handover/) — post-merge sweep and the Teams message.
- [week 17 bump triage](skills/therock-bump-pr-triage/examples/week17-0427/) — failed jobs mapped to existing issues.
- [week 36 override rotation](skills/process-merge-override/examples/week36-override-rotation/) — acquire, triage, merge, and the two build-break mistakes behind the Hard rule.

## Layout

```
skills/<skill-name>/
  SKILL.md            # frontmatter name matches the directory
  skill-card.md       # description, owner, license
  evals/evals.json    # routing and behavior cases
  reference.md        # optional; linked from SKILL.md
  scripts/            # optional
  examples/           # optional
.cursor/commands/     # optional Cursor shortcuts
.claude-plugin/  .cursor-plugin/  .codex-plugin/  .agents/plugins/   # plugin manifests
```

## Contributing

1. Add `skills/<name>/` with `SKILL.md`, `skill-card.md`, and `evals/evals.json`.
2. `name` is lowercase-with-hyphens, matches the directory, and the description says what the skill produces and when to use it.
3. Keep the `SKILL.md` body at or under 500 lines. Put the long procedure in `reference.md` and link it from `SKILL.md`.
4. `evals/evals.json` needs at least 3 cases with `skill_should_trigger: true` and 2 with `false`. A `false` case has only `id` and `prompt`. At least one `true` case grades behavior.
5. Update the catalog table in this README. To bundle the skill in the plugin, add its path to the `skills` list in all three manifests (`.claude-plugin`, `.cursor-plugin`, `.codex-plugin`).

Public-content rules:

- No internal hostnames, credentials, or dashboard URLs. Use a placeholder and point at the internal page.
- No roster that maps a colleague's name to a GitHub login. Publish the method for finding the reviewer.
- Every claim about a gate or a required check ships with the command that re-checks it.

## License

[MIT](LICENSE). Skill cards name ROCm DevOps as the owner.
