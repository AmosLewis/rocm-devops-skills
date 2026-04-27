# Skill: Bump PR Gardener Triage

Daily bump PRs are created by bot: https://github.com/apps/assistant-librarian (every ~12 hours).

- **rocm-libraries** PR title format: `Bump rocm-libraries from <START_COMMIT> to <END_COMMIT>`
- **rocm-systems** PR title format: `Bump rocm-systems from <START_COMMIT> to <END_COMMIT>`

Repo: https://github.com/ROCm/TheRock

---

## 1. Triage Workflow (step by step)

### 1.1 Gather failed job links

The user provides one or both bump PR URLs (e.g. `https://github.com/ROCm/TheRock/pull/4839`). Use `gh` to automatically discover all failed jobs:

```bash
# Get the latest workflow run for the PR and list failed jobs
gh pr checks <PR_NUMBER> --repo ROCm/TheRock | grep -i "fail"

# Or get the run ID from the PR checks, then list failed jobs:
gh api "repos/ROCm/TheRock/actions/runs/<RUN_ID>/jobs?filter=latest&per_page=100" \
  --jq '.jobs[] | select(.conclusion == "failure") | "\(.name)\t\(.html_url)"'
```

If `gh pr checks` doesn't give enough detail, find the run ID from the PR's checks tab, then query jobs via the API. Extract the job IDs from the URLs (`.../job/<JOB_ID>`).

Save the failed job list and tracker to a working directory, e.g.:

```
<your-workspace>/triage/week<WW>/MMDD/<r-l PR>-<r-s PR>.md
```

The user may also directly provide a list of failed job URLs — in that case skip the auto-discovery step.

### 1.2 Fetch full job logs

Use `gh api` to pull the **complete raw log** for each failed job. **Do not** just tail the last few lines — search the full log for failure patterns.

```bash
gh api -H "Accept: application/vnd.github+json" \
  "repos/ROCm/TheRock/actions/jobs/<JOB_ID>/logs" > /tmp/job_<JOB_ID>.log
```

For very large logs (>5000 lines), also fetch the tail separately:

```bash
gh api -H "Accept: application/vnd.github+json" \
  "repos/ROCm/TheRock/actions/jobs/<JOB_ID>/logs" | tail -50
```

And use targeted searches through the full stream:

```bash
gh api -H "Accept: application/vnd.github+json" \
  "repos/ROCm/TheRock/actions/jobs/<JOB_ID>/logs" \
  | rg -i "tests passed|FAILED TESTS|SEH|CalledProcessError|exit code 1|reproduce_test_failure|timed out"
```

**Key search patterns:** `FAILED`, `SEH exception`, `0xc0000005`, `Fatal Error`, `CalledProcessError`, `timed out`, `tests passed`, `Complete job name`, `reproduce_test_failure`.

> **Note:** `gh run view --job <id> --log` may return empty in some environments. Always prefer `gh api .../jobs/<id>/logs`.

### 1.3 Compare with previous issues

Always load the **previous bump pair's tracker** and the [Confluence Bump Failure Tracking page](https://amd.atlassian.net/wiki/spaces/MLSE/pages/1621581386/Bump+Failure+Tracking+by+Component+and+Owner) to check if each failure matches an existing filed issue.

**Common existing issues (Windows gfx110X, as of late Apr 2026):**

| Component | Issue | Pattern |
|-----------|-------|---------|
| hipBLAS | [rocm-libraries#6620](https://github.com/ROCm/rocm-libraries/issues/6620) | `gemm_bad_arg`, `gemm_ex_bad_arg`, `syrk_ex` failures |
| hipBLASLt | [rocm-libraries#6726](https://github.com/ROCm/rocm-libraries/issues/6726) | 1717 FAILED / SEH 0xc0000005 |
| hipSOLVER | [rocm-libraries#6730](https://github.com/ROCm/rocm-libraries/issues/6730) | GETRF numerical accuracy (`testing_getrf.hpp:728`) |
| MIOpen (Win) | [rocm-libraries#6733](https://github.com/ROCm/rocm-libraries/issues/6733) | `ImplicitGemm3DGroup{Fwd,Bwd,Wrw}Xdlops` |
| rocWMMA | [rocm-libraries#6707](https://github.com/ROCm/rocm-libraries/issues/6707) | `gemm_*-validate` / `rocblas_status_internal_error` / Linux timeout >60m |
| libhipcxx_hipcc | [TheRock#4617](https://github.com/ROCm/TheRock/issues/4617) | `offload-arch` returns `None` → `CMAKE_HIP_ARCHITECTURES=None` |
| rocsolver | [rocm-libraries#6708](https://github.com/ROCm/rocm-libraries/issues/6708) | LAPACK GETRI shard timeout (~40 min) |
| MIOpen (Linux) | [rocm-systems#5430](https://github.com/ROCm/rocm-systems/issues/5430) | HIPRTC JIT ambiguous `__habs`/`hsqrt`/`__hisnan`, `reduce_custom_fp32_fp16` |
| hip-tests ROCR (Win, xfail) | [TheRock#3587](https://github.com/ROCm/TheRock/issues/3587) | Windows ROCR hip-tests transitional — jobs tagged `(xfail)`, still link the issue |

**Important:** Both r-l and r-s PRs run **Linux AND Windows** tests in their own workflow runs. Always check both platforms on both PRs. The Windows failures will typically be the same existing issues on both PRs — list them under each PR section in the Teams message.

**Ignore:** `Driver / GPU sanity check` errors in logs — not relevant for triage.

### 1.4 For genuinely NEW failures — create issue draft

Save a GitHub-issue-ready markdown file:

```
<your-workspace>/triage/week<WW>/MMDD/<PR>/<MMDD>-<platform>-<component>-pr<PR>-run<RUN_ID>-job<JOB_ID>-ci-issue.md
```

Include:
- Title: `[BumpPR] <Platform> <GPU> <component> — <short description>`
- Summary: PR, Run, Job links, component, platform, job name
- Failure details: raw error log snippets (a few representative lines)
- Reproduce command (from the CI footer `reproduce_test_failure.py` block)
- Notes: comparison with prior issues

**If the failure matches an existing issue:** do NOT create a new file. Mark it as **Existing** in the tracker with the issue link. Just comment on the existing issue with the new job URL if needed.

### 1.5 Create/update tracker file

**Always** create `<r-l PR>-<r-s PR>.md` — this is the primary triage artifact. It must be **GitHub-comment-ready** so you can copy-paste it directly into PR comments.

Include a table per platform with full details:

```markdown
| PR | Component | Run | Job | Status / notes |
|----|-----------|-----|-----|----------------|
| 4839 | rocsolver (shard 2/2) | [24971248865](run_url) | [73132705084](job_url) | **Existing** [rocm-libraries#6708](issue_url) — timeout 40 min |
```

- **Run** and **Job** columns must be clickable links (markdown `[id](url)` format).
- **Status** must include the issue link so it's clickable in GitHub comments.

Status should be one of:
- **NEW** — genuinely new, draft filed, link to draft
- **Existing** [repo#number](url) — matches known issue
- **(xfail)** [TheRock#3587](https://github.com/ROCm/TheRock/issues/3587) — expected failure, still link issue

### 1.6 Save Teams message

**Always** save the Teams triage update to:

```
<your-workspace>/triage/week<WW>/MMDD/<r-l PR>-<r-s PR>-teams.md
```

This is the copy-paste message for the **Gardening-Bump-PR** Teams channel.

Format:

```
Bump PR Tracker – DD Mon (Week: Mon DD–DD)

- rocm-libraries
  - PR: <url>
- rocm-systems
  - PR: <url>

Rocm-libraries:
- Linux: <status>
- Windows (gfx110X): <summary>
  - <component> (<N> FAILED): <issue url>
  - ...

Rocm-systems:
- Linux (gfx94X): <summary>
  - Old Issues:
    - <component>: <issue url>
  - CI Timeout:
    - <component>: <issue url>
  - New Issues:
    - <component>: <issue url or "draft filed">
- Windows (gfx110X): <summary>
  - <same existing issues as r-l>
```

**Always list old/existing issues in the report** — next gardener needs them as reference.

---

## 2. Confluence

Update the [Bump Failure Tracking by Component and Owner](https://amd.atlassian.net/wiki/spaces/MLSE/pages/1621581386/Bump+Failure+Tracking+by+Component+and+Owner) page when a genuinely new issue is filed. Check existing rows first to avoid duplicates; append new rows at the bottom using the same format.

---

## 3. Handling In-Progress / Pending Tests

Full CI takes **~8 hours**. When triaging, some tests may still be running or queued.

### 3.1 Mark pending tests in tracker

If `gh pr checks` shows jobs still `pending` or `in_progress`, add a row in the tracker:

```markdown
| 4839 | Windows tests | — | — | **PENDING** — still running, recheck later |
```

### 3.2 Background polling (optional)

Poll `gh pr checks` every 30 minutes until all jobs complete. When all jobs finish, update the tracker and Teams message with the final results.

```bash
gh pr checks <PR_NUMBER> --repo ROCm/TheRock --watch
```

In Cursor, you can ask the agent to launch a sub-agent that polls in the background.

### 3.3 Flaky / Infra failures — retrigger

If a failure looks like a **flaky infra issue** (e.g. `HSA_STATUS_ERROR_OUT_OF_RESOURCES`, `no ROCm-capable device`, random GPU hang not matching known patterns), **retrigger the failed job at least 2 times** before filing a new issue:

```bash
gh run rerun <RUN_ID> --repo ROCm/TheRock --failed
```

If it passes on retry, mark as **Flaky** in the tracker. If it fails consistently (2+ retries), then file a new issue.

---

## 4. Key Rules

1. **Fetch full logs** — never rely on just the tail. Use `gh api .../jobs/<id>/logs` (not `gh run view --job`).
2. **Always compare** with the previous bump tracker and existing GitHub issues before filing new ones.
3. **Delete triage draft files** if the failure matches an existing issue.
4. **Always generate the Teams message** (`-teams.md`) at the end of triage.
5. **Always list old issues** in the tracker and Teams message — the next gardener needs the reference.
6. **r-l = rocm-libraries**, **r-s = rocm-systems** shorthand in Teams.
7. Bump PR merge rule: if Linux passes and Windows failures are all existing/tracked, **r-l is ready to merge**. r-s may depend on r-l.
8. **Mark PENDING jobs** in the tracker if tests are still running. Recheck or poll until complete.
9. **Retrigger flaky infra failures** at least 2 times before filing new issues. Use `gh run rerun --failed`.

---

## 5. File Layout Example

```
triage/week17/0427/
├── 4839-4840.md              # main tracker (GitHub-comment-ready)
├── 4839-4840-teams.md        # Teams copy-paste message
├── 4839/                     # rocm-systems PR drafts (if any NEW)
│   └── 0427-linux-...-ci-issue.md
└── 4840/                     # rocm-libraries PR drafts (if any NEW)
    └── 0427-windows-...-ci-issue.md
```
