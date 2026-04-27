# tr — Bump PR Triage Command

> For use with **Cursor** custom commands (`/tr`) or as a prompt for **Claude CLI**.

Context: Read `gardener/bumppr_skill.md` first, then follow the triage workflow.

## Instructions

1. I will give you bump PR URLs (e.g. `https://github.com/ROCm/TheRock/pull/4839`) or a list of failed job links. If given PR URLs, use `gh` to auto-discover all failed jobs from the PR checks. Both r-l and r-s PRs run Linux AND Windows tests — check both.
2. Fetch full logs for each failed job using `gh api`. Search for failure patterns — do NOT just tail.
3. Compare each failure with the previous bump pair's tracker and existing GitHub issues.
4. If a failure matches an existing issue: mark as **Existing** in the tracker, do NOT create a triage draft file.
5. If a failure is genuinely NEW: create a GitHub-issue-ready .md draft. Include raw failure log snippets.
6. Ignore `Driver / GPU sanity check` in logs. Even for `(xfail)` jobs, link the tracking issue.
7. **Always** create `<r-l PR>-<r-s PR>.md` tracker with detailed tables (PR, Component, Run ID, Job ID, job URL, issue status). This file should be GitHub-comment-ready — I will directly copy-paste it into PR comments.
8. **Always** save a Teams copy-paste message to `<r-l PR>-<r-s PR>-teams.md` at the end, listing all failures with their issue links. Always list old/existing issues — next gardener needs the reference.
9. No need to save new skill files.

## Example usage

```
/tr https://github.com/ROCm/TheRock/pull/4839 https://github.com/ROCm/TheRock/pull/4840
```

Or with a list of failed job URLs:

```
/tr
rocsolver: https://github.com/ROCm/TheRock/actions/runs/24971248865/job/73132705084?pr=4839
miopen: https://github.com/ROCm/TheRock/actions/runs/24971248865/job/73132705012?pr=4839
```
