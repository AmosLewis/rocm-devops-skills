---
name: monorepo-gardener-triage
description: >-
  Classifies a blocked human pull request on ROCm/rocm-libraries or
  ROCm/rocm-systems. Reads merge state and that repo's required checks
  before any log, buckets each red as infra, code, zero-signal, or
  advisory, and writes a three-part public reply plus one tracker row.
  Use when a gardener hears "my PR is blocked", "can you bypass", or is
  asked to confirm CI failures on a monorepo PR. Do not use for bot bump
  PRs in ROCm/TheRock (therock-bump-pr-triage), the Tuesday handover
  (gardener-rotation-handover), pulling Teams requests
  (teams-gardener-requests), or executing the merge
  (process-merge-override).
---

# Skill: Monorepo Gardener — PR and post-submit triage

For the **ROCm/rocm-libraries** and **ROCm/rocm-systems** gardener rotation, when someone says *"my PR
is blocked, can a gardener look?"* in the gardening channel or on the PR thread.

Companion skills: [`therock-bump-pr-triage`](../therock-bump-pr-triage/SKILL.md) covers the bot-generated bump PRs in
ROCm/TheRock, and [`gardener-rotation-handover`](../gardener-rotation-handover/SKILL.md) covers the last day of your rotation —
the batch post-merge sweep and the handoff artifacts. [`teams-gardener-requests`](../teams-gardener-requests/SKILL.md) only lists the week's asks. [`process-merge-override`](../process-merge-override/SKILL.md) executes a bypass after this skill has classified it. This file covers the classification: human PRs blocked by CI, bypass requests, and post-submit reds.

**Normative policy** lives in each repo's own doc and wins over anything here:

- [rocm-libraries/docs/gardening.md](https://github.com/ROCm/rocm-libraries/blob/develop/docs/gardening.md)
- [rocm-systems/docs/gardening.md](https://github.com/ROCm/rocm-systems/blob/develop/docs/gardening.md)
- [RFC0002 MonoRepo Gardener Rotations](https://github.com/ROCm/TheRock/blob/main/docs/rfcs/RFC0002-MonoRepo-Gardener-Rotations.md)

This file is the **executable layer**: the exact `gh` recipes, the traps that produce wrong verdicts,
and the shape of the artifacts you hand back.

**Role boundary.** You are a facilitator for CI/infra triage, not the component code owner. Your
deliverable is a classification backed by links, plus the owner of the next step. You never vouch for
numerics, performance, or component code correctness.

## Contents

Sections 0–4 and 11 below are the path for every request. The proofs, the re-run rule, Math CI, approval routing, bypass execution, a queue-wide fault, and the trap list are in [reference.md](reference.md). Read that section before you use it.

| Section | Where |
| --- | --- |
| 0–4, 11, 13 | this file |
| 5. Hard proofs | [reference.md](reference.md) |
| 6. Re-run, re-dispatch, or push | [reference.md](reference.md) |
| 7. Math CI Summary | [reference.md](reference.md) |
| 8. Approval-blocked | [reference.md](reference.md) |
| 9. Bypass | [reference.md](reference.md) |
| 10. One fault blocks the queue | [reference.md](reference.md) |
| 12. Trap list | [reference.md](reference.md) |

## If you read nothing else

1. **Read state before reading logs** (§0). Most requests end at `mergeStateStatus` + the required set.
2. **The required set is per repo and per branch.** Enumerate it; the two repos differ (§1).
3. **A re-run replays the same merge commit.** It cannot pick up a `develop` fix — that needs a fresh
   dispatch or a push ([reference.md](reference.md) §6).
4. **A job that died in checkout or setup is zero signal**, neither failure evidence nor proof the
   change is sound (§3).
5. **"It passed on a re-run" is the weak argument.** Prefer an unreachable diff or a sibling job in the
   same run on the same commit ([reference.md](reference.md) §5).
6. **Ask whether waiting fixes it** before spending a bypass, and re-pull live state right before you
   execute one ([reference.md](reference.md) §9).
7. **A bypass is not done when it merges.** Sweep the merge commit — that is where the evidence you
   knowingly skipped finally shows up, and where a dropped mirror becomes visible ([reference.md](reference.md) §9,
   [`gardener-rotation-handover`](../gardener-rotation-handover/SKILL.md)).

---

## 0. The 60-second triage — read state before reading logs

Most requests end here. Reading logs first is the single biggest time sink in this role.

```bash
REPO=ROCm/rocm-libraries      # or ROCm/rocm-systems
PR=<number>

# a) required contexts on the base branch (no admin rights needed)
gh api repos/$REPO/rulesets --jq '.[] | "\(.id) \(.name) \(.target)"'
gh api repos/$REPO/rulesets/<RULESET_ID> \
  --jq '[.rules[] | select(.type=="required_status_checks")
         | .parameters.required_status_checks[].context]'

# b) is a bypass even the question?
gh pr view $PR --repo $REPO \
  --json mergeStateStatus,reviewDecision,headRefOid,autoMergeRequest,isDraft

# c) current state of every check
gh pr checks $PR --repo $REPO
```

| `mergeStateStatus` | `reviewDecision` | What it means | Your output |
| --- | --- | --- | --- |
| `BLOCKED` | `REVIEW_REQUIRED` | Review missing | Route to CODEOWNERS (§8). **Nothing to bypass** |
| `BLOCKED` | `APPROVED` | A required check is red, or never reported | The bypass case (§9) |
| `UNSTABLE` | `APPROVED` | Every red is advisory | Tell the author to squash it themselves. Do not touch `--admin` |
| `BEHIND` / `DIRTY` | any | Needs update or has conflicts | Author's job |
| `CLEAN` | `APPROVED` | Green | Nothing to do |

**Classify the ask, not just the PR.** *"Can you confirm these failures are unrelated?"* is a request
for **analysis**. Answering it with an offer to bypass is a different, larger commitment than what was
asked. Also check whether the author already solved it: auto-merge enabled means green checks merge
themselves and you are not needed.

```bash
gh api repos/$REPO/issues/$PR/timeline --paginate \
  --jq '.[] | select(.event|test("auto_squash_enabled|head_ref_force_pushed|committed")) | .event'
```

---

## 1. The required set differs per repo *and* per target branch

Verified 2026-08-10 — enumerate rather than trust this table, ruleset contents change:

| Repo | Branch (ruleset) | Required contexts |
| --- | --- | --- |
| rocm-libraries | `develop` (5167088) | `TheRock CI Summary`, `Math CI Summary`, `pre-commit` |
| rocm-systems | `develop` (9297053) | `TheRock CI Summary`, `HIP NVIDIA CI Summary` — **no `pre-commit`, no Math CI** |
| rocm-systems | `rocprofiler-compute` (16665354) | `TheRock CI Summary` only |

The two `gardening.md` files differ by about six lines, which makes it very easy to assume the gates
match. They do not. Run the `rulesets` query on every repo you take over.

Other rules worth knowing on rocm-libraries `develop`, all readable without admin:

```bash
gh api repos/$REPO/rulesets/<ID> --jq '{bypass:.bypass_actors, rules:[.rules[]|{type,parameters}]}'
```

| Rule | Value |
| --- | --- |
| `require_code_owner_review` | `true`, `required_approving_review_count: 1` |
| `dismiss_stale_reviews_on_push`, `require_last_push_approval` | both `false` → a push or rebase does **not** drop approval |
| `required_review_thread_resolution` | `true` → an unresolved review thread blocks the merge too |
| `allowed_merge_methods` | `squash`, `rebase` |

`bypass_actors` reading as `[]` does **not** mean you cannot bypass — the field is flattened for
non-admins, and `collaborators/<me>/permission` reports only `write`. Judge your own ability from
history (`gh pr view <PR> --json mergedBy` on something you pushed through), not from those fields.

**Everything outside the required set is advisory**: packaging install lanes, coverage thresholds,
`Multi-Arch CI Summary`, `codecov/project/*`. Worth an issue, never worth a bypass.

---

## 2. Confirm the data is current and complete before analysing it

Four ways the API will hand you a wrong picture:

**a) The run has not finished.** A verdict read off an in-progress run is not a verdict.

```bash
gh api repos/$REPO/actions/runs/<RUN_ID> --jq '{run_attempt,status,conclusion,created_at}'
```

If it is still going, look only at the required set. If nothing there has failed yet, **stop and
wait** — do not spend a pass classifying in-flight advisory reds, and do not hand back a conditional
*"if it goes green then X, otherwise Y"* answer that waiting resolves for free. A queued lane can flip
the whole conclusion: on one PR a `Build` lane went from an infra timeout to `success` on the same
commit, which turned its sibling's timeout into a *provable* flake rather than a suspicion.

**b) `runs/<id>/jobs` returns the latest attempt only.** Any re-run erases the earlier failures. The
list the reporter pasted may be the corpse of attempt 1.

```bash
gh api "repos/$REPO/actions/runs/<RUN_ID>/attempts/1/jobs?per_page=100" \
  --jq '.jobs[] | select(.conclusion!="success") | "\(.id) | \(.conclusion) | \(.name)"'
```

**c) Pagination.** `head_sha` queries get buried under dozens of unrelated runs (docs previews,
comment-triggered workflows). Check `.total_count` first; if it exceeds `per_page`, `--paginate` is
mandatory, not an optimisation. Skipping it once produced "28 commits were never mirrored", all false.

```bash
gh api "repos/$REPO/actions/runs?head_sha=$SHA&per_page=100" --paginate \
  --jq '.workflow_runs[] | "\(.name) | \(.event) | \(.conclusion)"'
```

**d) `statusCheckRollup` returns superseded check runs.** The same check name appears once per re-run,
old failures included. Counting `conclusion=="FAILURE"` reports a green PR as red. Group by name and
keep the newest `startedAt`. Note also that `Math CI Summary` is a `StatusContext`, not a `CheckRun` —
its verdict is in `.state`, and reading `.conclusion` yields `null`, which looks like "pending" and
mislabels a green authoritative gate.

```bash
gh pr view $PR --repo $REPO --json statusCheckRollup --jq '
  [.statusCheckRollup[]? | {name:(.name // .context), c:(.conclusion // .state // .status), t:.startedAt}]
  | group_by(.name) | map(max_by(.t)) | map(select(.c != "SUCCESS" and .c != "SKIPPED"))'
```

A `cancelled` conclusion is not a failure — concurrency cancellation shows up in the rollup and means
nothing. And a change in the *number* of reds is not a change in kind: one PR went from 3 reds to 14
purely because codecov expanded `codecov/project/*` from 2 flags to 11. Write the glob in your reply,
not the count, and the conclusion survives the next expansion.

---

## 3. Classify every red into one of four buckets

| Bucket | Meaning | Action |
| --- | --- | --- |
| **Infra / flaky** | Known issue, or reproduces off this branch | Link the issue, support a re-run or bypass |
| **Code-related** | The diff plausibly causes it | Route to CODEOWNERS with the isolated error |
| **No result (zero signal)** | The job died before test code ran | **Not** evidence of failure, and **not** evidence the change is sound |
| **Advisory** | Outside the required set | File an issue if untracked; never a bypass reason |

The zero-signal bucket is the one people get wrong. It is not "unrelated" — it is *absent*. Prove it
from the failing step's name and timestamps, not from the job conclusion:

```bash
gh api repos/$REPO/actions/jobs/<JOB_ID> \
  --jq '{name,started_at,completed_at,
         steps:[.steps[]|select(.conclusion!="success")|{name,conclusion,started_at}]}'
```

| Symptom | Read it as |
| --- | --- |
| Died in checkout, container setup, or action download | No result |
| `Executing the custom container implementation failed` | The self-hosted runner wrapper reporting a killed step. Read the timestamps above it |
| Gap exactly equal to a step timeout (e.g. 30.0 min) | Infra timeout — points at a specific `timeout-minutes` |
| `CMake Error` immediately above the wrapper message | A real build error |
| A `Summary` check is red | An aggregate. Count jobs before calling a lane dead |
| Scattered shards fail while siblings pass | Resource contention or throttling |
| A whole lane fails identically | Not throttling — look for a real cause |
| `echo "ERROR: ..."` with colour codes | The runner echoing script text, not an error |

Two more that repeat:

- **`Test (...)` showing `skipping` has two causes with opposite handling.** If the upstream build is
  green, the matrix genuinely does not run that arch — state the coverage gap honestly. If the
  upstream build is red, there was no artifact, so re-running the build brings the tests back. On one
  PR, waiting produced 18 test jobs including 6 component shards that an immediate bypass would have
  skipped entirely.
- **Cascades are not separate faults.** After a killed step, `therock_manifest.json not found`,
  `du: cannot access .../build/dist/rocm`, and `notify_teams.py: No such file or directory` are all
  downstream echoes. Do not list them in the thread as findings.

`fatal: early EOF` deserves its own note, because it says *"the stream was truncated"* and nothing
about why. `error: N bytes of body are still expected` (HTTP), `unexpected disconnect while reading
sideband packet` (git protocol), `fatal: early EOF` (`index-pack`) and `fatal: fetch-pack: invalid
index-pack output` (parent process) are four layers of one event. Truncation can also come from disk
pressure or an OOM-killed `index-pack`, so corroborate before calling it network: the same job failing
identically on all retries, independent jobs hitting it simultaneously, measured throughput in the log
(`kB/s`), or a control lane on a different network path cloning the same SHA in seconds. The sharpest
read is the trend in *bytes still missing*: 56230 → 36355 → 835 over three ~65-minute attempts means
it was throttled to death just short of the finish line, not disconnected.

---

## 4. Find the existing issue — by error text, across both repos

**Rule out a GitHub platform incident first.** With any of these, a cross-repo search returns zero
results because the cause is not in ROCm at all:

```text
Failed to resolve action download info
Error: Service Unavailable / Internal Server Error / Bad Gateway
The HTTP request timed out after 00:01:40
```

Criterion: the failure is in `Prepare all required actions` / `Getting action download info`, so not
one line of project code ran. Confirm in one second:

```bash
curl -s https://www.githubstatus.com/api/v2/summary.json | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('status:', d['status']['description'])
for c in d['components']:
    if c['status']!='operational': print('COMPONENT:', c['name'], c['status'])
for i in d['incidents']:
    print('INCIDENT:', i['name'], i['status'], i['created_at'], i['shortlink'])
"
```

During an outage, neither re-run nor bypass is the answer — wait for recovery, then re-run. (Unless it
drags: see the review points in §9.)

Otherwise search **both repos, by error text, not by label**:

```bash
gh search issues "<error text>" --repo ROCm/rocm-libraries --repo ROCm/rocm-systems \
  --repo ROCm/TheRock --state open
```

Why TheRock: it owns the build, the packaging and the TheRock-driven lanes, so a failure surfacing on
a monorepo PR is frequently already filed there. Its issues often sit on a triage board with **no
labels at all**, and its infra labels are `infra`, `infra-timeout`, `infra-machine`, `test-infra`,
`test-flaky` — not `gardener`. A `label:gardener` search is guaranteed to miss them. One real case, a
packaging lane 404-ing on every RPM, was only findable by cross-repo text search.

---

## 11. What you hand back

Three artifacts, and keeping them separate is what stops the tracker from growing to a thousand lines.

| Artifact | Path convention | Contains |
| --- | --- | --- |
| Public reply | `triage/week<WW>/MMDD-pr<PR>-respond.md` | Exactly what gets posted, one file per PR |
| Triage note | `triage/week<WW>/MMDD-pr<PR>-<topic>.md` | *Why* — evidence, log excerpts, timings |
| Weekly tracker | `triage/week<WW>/tracker.md` | One table **row** per PR. Never a prose section |

**The reply has a fixed shape, and it is three parts, nothing else:**

1. **One or two sentences: conclusion plus decision.** Lead with machine-readable state where one
   exists — *"`mergeStateStatus: UNSTABLE` and `reviewDecision: APPROVED`, so you can squash normally,
   nothing for me to `--admin`"*.
2. **A `| Red check | Keypoint |` table.** One row per red; keypoint is one clause of mechanism plus
   the known-issue link. **Never prose out a list of reds** — a semicolon-joined list is the single
   most common way these replies become unreadable. Collapse everything advisory into one row:
   *"sles16, `Multi-Arch CI Summary`, `codecov/project/*` — outside the required set"*.
3. **At most one closing sentence** naming a coverage gap you are choosing to state. Skip it when
   there is none.

Everything else — the required set member by member, the uncollapsed red table with timestamps and job
ids, log excerpts, the "why not just wait" argument — goes below a `# Optional detail` heading in the
same file, quoted only if someone pushes back. Add an `## If someone pushes back` section listing
which evidence to escalate with, so it is one click away instead of pre-pasted.

Writing rules that matter more than they look:

- **No pronouns or vague references.** "Both runs finished", "all the checks", "the earlier failure"
  are defects. Name the run with its id and link, name the check, name the commit. If a sentence would
  prompt *"which one?"*, it is not ready to send.
- **Do not explain what the author's patch does** — they wrote it. Do not walk through your
  investigation, list every green lane, or justify your method.
- **Skip the disclaimer by default.** Add the "not signing off on" line only when someone is pushing a
  non-CI problem onto you (numerics, performance, component code review).
- Acknowledge an existing approval as valid before explaining why it does not satisfy the rule.
  Nobody reads past feeling dismissed.
- If you posted something wrong, correct it in the same thread. A wrong conclusion left standing can
  tie a mergeable PR to an unrelated one for days.

### Reply templates

**Need a pointer**

```text
Could you share the exact run URL and job URL (and roughly when)? I'll read the full logs and confirm
whether this is infra or a real code failure.
```

**Known infra**

```text
This failure matches <issue link> — <one clause of mechanism>. It is not introduced by this change:
<the unreachable-diff or same-run-control evidence>. Suggested path: <fresh dispatch / re-run /
bypass>, tracked under <issue link>.
```

**Code-related**

```text
From the logs this is component code rather than infra: <isolated error, file:line>. Looping in the
owners for direction: <1-2 named people, with why>. I'll keep helping on CI signal and re-runs.
```

**Coverage gap (reusable wording)**

```text
I'm signing off on the CI signal interpretation and the infra classification, not on the <arch>
numerics or performance.
```

---

## 13. Wiring it into Cursor or Claude

See the [README](../../README.md). The Cursor command is
[`.cursor/commands/gr.md`](../../.cursor/commands/gr.md). Loading this folder is enough; the command
is only a shortcut. For Claude CLI, pass this file with `--file` or copy it to `CLAUDE.md`.

On the last day of your rotation, switch to `/ho`
([`gardener-rotation-handover`](../gardener-rotation-handover/SKILL.md)) for the post-merge sweep and the handoff artifacts.
