---
name: process-merge-override
description: Process a merge-override / bypass-merge request for one ROCm/rocm-systems or ROCm/rocm-libraries PR whose only required-gate check failures are known infra flakes. Verifies the four bypass preconditions, runs the common-vs-distinctive failure triage to rule out code causes, posts a #10579-style rationale comment, then merges past the failing required gate (single PR via `gh pr merge --admin`; stacked PR via the CDP `enqueue_stack` driver), verifies MERGED, and hands back a Teams "Merged!" reply that always includes the Teams thread permalink. When the ask covers several PRs (a stack, a list, or a "process the open override requests" sweep), it first emits a verdict report table - one row per open PR with the GitHub PR link, the Teams discussion permalink, and a can/cannot verdict - and asks which to merge before executing. Use when a gardener is asked to force-merge / override / bypass a blocked PR. Companion to monorepo-gardener.
---

# Skill: Process a merge-override request

For the **ROCm/rocm-systems** and **ROCm/rocm-libraries** gardener rotation, when someone asks you to
**override / force-merge / bypass** a PR that is `BLOCKED` because a *required* gate is failing on what
they believe are known infra flakes (e.g. in the gardening Teams channel or on the PR thread).

This is the **execution** counterpart to [`monorepo_gardener_skill.md`](monorepo_gardener_skill.md): that
skill classifies a blocked PR; this one takes the decision-to-override through to a verified merge and
a posted rationale. The normative policy is each repo's own `docs/gardening.md` and wins over anything
here. **You are a facilitator for CI/infra triage, not the component code owner** - you sign off on the
infra classification, never on numerics, performance, or component-code correctness.

Scripts referenced below live in `scripts/` next to this file. All are dry-run by default.

## Quick commands (the typical /pmo flow)

Terse cheat-sheet; each step is explained in full below. All scripts are dry-run until you add `--go`.
Repo is `ROCm/rocm-systems` or `ROCm/rocm-libraries`.

```bash
# 0. Pull the week's asks from Teams (read-only) -> table with PR state + permalinks
python ../teams_gardener_requests_skill scripts/pull_gardener_requests.py --hours 72 --merge-only --md sweep.md

# 1. Resolve the TRUE approval axis (trust this, NOT raw reviewDecision). Only APPROVED is bypassable.
python scripts/check_approval.py <PR> --repo <REPO>        # APPROVED | PARTIAL | NOT_APPROVED | CHANGES_REQUESTED

# 2. Confirm shape: base==develop AND no children == single (--admin). Else stacked (enqueue_bypass.py).
gh pr view <PR> --repo <REPO> --json baseRefName,headRefName,state,mergeStateStatus,isDraft
gh pr list --repo <REPO> --base <this PR's headRefName> --state open --json number   # children? -> stacked

# 3. Prove failing required lanes are infra. Batch several PRs = free cross-check (COMMON lane == infra).
python scripts/garden_triage.py --prs <PR1>,<PR2>,<PR3> --repo <REPO> --deep
gh pr view <PR> --repo <REPO> --json files --jq '.files[].path'   # match each distinctive fail to the diff

# 4a. SINGLE PR: dry-run the rationale, read it, then re-run with --go to comment + admin-merge.
python scripts/garden_bypass_single.py <PR> --repo <REPO> \
  --unrelated '<what the diff actually is>' \
  --fails 'Job A: reason' --fails 'Job B: reason'   # one --fails per lane; every entry NEEDS a colon
#   ...append --go to execute;  add --ack-build-failure-is-infra ONLY for a build step you proved infra from the log

# 4b. STACKED PR: needs authenticated CDP Chrome on :9222; merge bottom -> top, one at a time.
python scripts/enqueue_bypass.py <BOTTOM_PR>        # dry run (refuses unless base==develop)
python scripts/enqueue_bypass.py <BOTTOM_PR> --go   # irreversible; poll to MERGED, then repeat up the stack

# 5. Post-merge sweep of the merge SHA. total_count==0 here is a dropped-push FINDING, not silence.
gh api "repos/<REPO>/actions/runs?head_sha=<merge_sha>&per_page=100" --paginate \
  --jq '.workflow_runs[] | select(.event!="issue_comment") | "\(.event) \(.name) \(.conclusion)"'
```

Hand back the script's paste-ready `Merged! <comment-url>` line **with** the PR's Teams thread
permalink. Batch ask (several PRs)? Report the verdict table first and let the gardener pick - see below.

## When asked to process a *batch* (several PRs, "process these", or a fresh sweep): report first

If the ask covers **more than one** PR - a stack, a list, or a "process the open override
requests" sweep - do **not** start merging. First triage every PR (Steps 0-1) and emit the
**verdict report table** (Step 1B): one row per OPEN request PR with its **GitHub PR link**, the
**Teams discussion permalink**, and a can/cannot **verdict + reason**. Present that table and let the
gardener pick which eligible PRs to merge before you execute anything. A single named PR
("/process-merge-override 10487") skips straight to Step 0 for that PR.

## Hard rule - a failing BUILD/COMPILE step is never bypass-eligible unless it is definitively infra

This overrides everything below. If a *required*-gate failure happened **inside the build/compile
step**, you may not override it unless you have proven from the log that it is an infrastructure
failure (fetch/clone/network, toolchain or container provisioning, runner death - i.e. something that
died **before the compiler ran**). A compiler/linker/`static_assert` error **is the PR's code failing
to build** and blocks the merge, full stop - route it to CODEOWNERS or get it reverted; do not bypass.

- **Never take the requester's or author's word that failures are "unrelated" / "just script
  failures."** That is a claim to verify, not evidence. Open the actual build log and read the first
  error line yourself. A green "trust me" from the person asking you to merge is worth nothing against
  a failing build step.
- **Build-step failure => presumed code-caused.** The burden is on proving infra, not on proving code.
  If you cannot definitively show it is infra, treat it as code and refuse the override.
- Distinguish from the log, not the conclusion: `error:`, `static assertion failed`, `undefined
  reference`, `ld: `, a `CMake Error` at the compile/link stage = **code**. "Fetch sources" timeout,
  clone/network error, container/toolchain provisioning, runner offline = **infra** (and only these are
  bypass-eligible for a build step).

**Incident this rule comes from (rocm-systems #10179, 2026-08).** A gardener was asked to merge an
approved PR with "a few CI failures"; asked "these are unrelated right?", the author answered "those
are some script run failures", and it was merged on that word. The failure was in fact a real compile
break - a `kBlockNameMap` `static_assert` in `projects/rdc/tests/rdc_tests/test_common.cc` tripped by
the PR's amdsmi GPU-block enum expansion. It landed on `develop`, broke the RDC build for **everyone**
(and later surfaced as the "develop-level" `kBlockNameMap` failure in other triage), and had to be
reverted (#10947) with a tracking issue filed. The owners' explicit correction: *"please do not take
developers' word for build compilation issues; CI failures for build should never be treated as
un-related."* Had this rule been applied, #10179 would not have been overridden.

## Known infra-flake catalog (verify each still matches the log, then cite the precedent)

> **Rotation-scoped snapshot - expect this to drift.** The entries below are the recurring,
> log-confirmed infra failures observed during the **week-36 / early-Sept-2026** rotation. Known flakes
> are **not permanent**: a lane listed here can be fixed, re-tuned, or retired between rotations, and a
> genuinely *new* code failure can start wearing the same lane name. Treat this list as a time-stamped
> hint, never as standing authority - **always re-open the current log and confirm the signature still
> matches before citing an entry**, and when you inherit or hand off the rotation, re-baseline it (prune
> what's fixed, add what's newly proven, update the "Last confirmed" date). Each entry carries the
> dates/PRs where it was last proven so a later gardener can tell how stale it is.

These are the recurring, log-confirmed infra failures seen this rotation. A matching signature is
strong, precedent-backed evidence the lane is infra and gives you concrete `--fails` wording - but it is
evidence to confirm against today's log, not a license to skip reading it.

- **Windows amd-mesa third-party build (`lua` toolchain)** - job `Windows (gfxNNNN) / Build Windows
  Packages`, failing step `Build therock-artifacts and therock-dist`. Log signature (read it to confirm):
  `[therock-amd-mesa] ... Run-time dependency lua54 / lua-5.4 found: NO (tried pkg-config and cmake)`
  then `[therock-amd-mesa] Preliminary CMake check failed. Aborting.` and
  `FAILED: .../amd-mesa/build/stamp/build.stamp`. This is a **third-party sub-project** whose meson
  build cannot find `lua` on the runner - it dies **before any PR code is compiled**, so it is toolchain
  provisioning, not the diff. The many `LNK2019` lines under `[therock-amd-mesa]` are meson's own
  compiler-feature probe files (`testfile.obj` in `meson-private\tmp...`), not the PR's code - do not
  mistake them for a link break in the diff. It rolls the retired **`TheRock CI Summary`** red while the
  migrated **`Multi-Arch CI Summary` stays green**. This is the one legitimate
  `--ack-build-failure-is-infra` case (the reason text trips the compile regex, but the log proves
  infra). Caveat to state honestly: if the PR itself changes Windows code, the Windows build dying in
  amd-mesa means the PR's Windows path was **never validated** - flag that coverage gap to the author,
  even though the failing gate is infra. _Last confirmed: 2026-09-02 (#9836, #9042, #10034)._

- **`Merged PR to Patch Subrepos` failing on the merge SHA (post-submit)** - a known, recurring red on
  the subrepo-mirror workflow (failing step `Generate and apply patches`). Seen failing on the #10572
  and #9836 merge SHAs while #11033's went green the same day - i.e. it is flaky and **not** caused by
  your specific bypass. Glance at it during the Step-4 sweep, but a lone failure here is not evidence
  your merge broke `develop`. (Distinct from `total_count == 0`, which is a genuine dropped-push
  finding.) _Last confirmed: 2026-09-02 (#10572, #9836)._

- **MI455 hip-tests / rocrtst container-init deaths** - `Linux MI455 Test / Test hip-tests` and
  `Test rocrtst` frequently die in container/OCI setup (exit 137, `setns` errors, `Initialize
  containers`, harness aborting ~2s after start). When the **same** lane fails across several unrelated
  diffs in one triage batch (COMMON), that is shared-environment infra by definition, not any one diff.
  _Last confirmed: 2026-09-02 (COMMON across #9243, #10034, #10790, #11033)._

## The one thing that decides everything: single vs stacked

The PR's shape picks the merge tool. Get this wrong and the merge silently no-ops or 404s.

| PR shape | How to detect | Bypass tool | Auth |
| --- | --- | --- | --- |
| **Single** (base is `develop` **and** no child PRs) | `baseRefName == develop` **and** no open PR has `baseRefName == <this PR's headRefName>` | `gh pr merge <PR> --merge --admin` | gh token, **no browser** |
| **Stacked** (base is another PR's branch, **or** it has children on its head) | `baseRefName` is some `feature/...` branch, **or** another open PR targets its head | `enqueue_bypass.py <PR> --go` (CDP `enqueue_stack`) | authenticated Chrome on `:9222` |

```bash
gh pr view <PR> --repo <REPO> --json baseRefName,headRefName,state,mergeStateStatus,reviewDecision,isDraft
# base==develop is necessary but NOT sufficient - also confirm nothing is stacked ON it:
gh pr list --repo <REPO> --base <this PR's headRefName> --state open --json number
```

> **`base == develop` is not enough.** If any open PR is based on *this* PR's head branch, GitHub
> treats it as a **stack** and `--admin` / merge-async is refused with *"part of a stack and must be
> merged using the asynchronous merge REST API"* - even though the base is `develop`. Always run the
> children check above; only a PR that is base==develop **and** childless is a true single.

> **Endpoint drift (2026-09):** the CDP `enqueue_stack` **write** endpoint has returned **401** even
> with a valid verified-fetch nonce (verified-fetch *reads* - `page_data/merge_box` GET - still 200,
> confirming the nonce/headers are fine). GitHub moved/renamed the stacked-merge write path. When this
> happens, `enqueue_bypass.py` cannot land the merge; re-capture the current request the web "bypass
> rules" merge issues (Network log while a human clicks it) and update the driver's URL/payload. Do
> **not** force the merge through fragile click-automation - the merge is irreversible.

- On a **single** PR, `--admin` merges straight past a failing required gate. `enqueue_stack` **404s**
  on a single PR - do not use it there.
- On a **stacked** PR, `--admin` / merge-async is refused with *"Required status check ... is failing"*.
  You must drive the web "bypass rules" path via `enqueue_bypass.py`, merging **bottom -> top**, one PR
  at a time, re-pointing each child's base to `develop` as its parent lands.

`gh` (token) survives a browser sign-out; **CDP does not**. If you'll need the stacked path, confirm
Chrome is up and signed into GitHub first (see section Stacked execution).

## Step 0 - Confirm this is actually a bypass case (don't open a log yet)

```bash
REPO=ROCm/rocm-systems   # or ROCm/rocm-libraries
PR=<number>
gh pr view $PR --repo $REPO --json state,mergeStateStatus,reviewDecision,isDraft,baseRefName,autoMergeRequest
```

> **Do NOT gate on `reviewDecision` alone - it lies.** GitHub returns an **empty/null**
> `reviewDecision` even when code owners **have** approved (common when CODEOWNERS spans several owner
> teams: some approve while others stay auto-requested). Treating empty as "not approved" hides real
> approvals and mislabels the PR. Always resolve the true state with the helper, which reads
> `latestOpinionatedReviews` + outstanding codeowner `reviewRequests`:
> ```bash
> python scripts\check_approval.py $PR --repo $REPO   # -> APPROVED | PARTIAL | NOT_APPROVED | CHANGES_REQUESTED
> ```
> | check_approval verdict | Meaning | Bypass on review axis? |
> | --- | --- | --- |
> | `APPROVED` | all required owners satisfied, no changes requested | eligible -> continue |
> | `PARTIAL` | approvals exist but at least one changed file's governing CODEOWNERS rule is still unsatisfied (per-file resolution; a still-requested *same-line alternate* is **not** a PARTIAL) | **No** - route the owners of the uncovered files |
> | `NOT_APPROVED` | `REVIEW_REQUIRED` or no standing approval | **No** - route to CODEOWNERS |
> | `CHANGES_REQUESTED` | a reviewer's latest stance is changes-requested | **No** - hard stop |
>
> A gardener bypass is for known-infra/flaky **CI**, **never** for unmet code review. Only `APPROVED`
> clears the review axis; everything else routes to CODEOWNERS regardless of the CI state.

> **The false-PARTIAL trap (one approval on a multi-owner line is enough).** A CODEOWNERS line lists a
> *set* of owners, and under GitHub semantics **one approval from anyone on the governing line satisfies
> the code-owner requirement for that file**. GitHub still auto-requests the *other* owners on that same
> line, and they linger in `reviewRequests` as "still requested" even though they are **not** separately
> required. A naive "there are approvals AND still-outstanding reviewers => PARTIAL" therefore *falsely
> blocks* a PR whose review is actually complete. `check_approval.py` now resolves this **per file**: for
> a null-decision PARTIAL it fetches the PR's changed files + the repo `CODEOWNERS`, finds each file's
> governing rule (**last matching pattern wins**), and upgrades to `APPROVED` only when **every** changed
> file is already covered by an approving user-owner or a team-owner with an approving member. If any file
> is still uncovered it stays `PARTIAL` and names the file + its owners; if a team's membership can't be
> read it says so (verify by hand before trusting). Confirm the reasoning yourself when it matters:
> ```bash
> python scripts\check_approval.py $PR --repo $REPO --json   # shows the per-file "codeowners" resolution
> gh pr view $PR --repo $REPO --json files --jq '.files[].path'   # the changed files
> gh api repos/$REPO/contents/.github/CODEOWNERS --jq '.content' | base64 -d   # the rules (last match wins)
> ```
> Incident this fixes (rocm-systems **#7125**, 2026-09): every changed file was under the single line
> `/projects/rocr-runtime/ @kentrussell @dayatsin-amd @cfreeamd @atgutier @shwetagkhatri`; dayatsin-amd
> and cfreeamd (both on that line) approved, so review was satisfied and `reviewDecision` was null. The
> old flat rule mislabelled it PARTIAL. (It was still correctly refused - but on the **CI axis** for a
> real build break, not on review. Getting the axis right matters: route review problems to CODEOWNERS,
> route CI problems per the Hard rule.) `--no-codeowners` disables the resolution if you want the raw flat
> verdict.

| `mergeStateStatus` / approval (via `check_approval.py`, not raw `reviewDecision`) | Verdict |
| --- | --- |
| `BLOCKED` + `NOT_APPROVED`/`PARTIAL`/`CHANGES_REQUESTED` | Review-blocked, **not** a bypass. Route to CODEOWNERS (name the outstanding owners). Stop. |
| `UNSTABLE` + `APPROVED` | Every failing check is advisory - author squashes it themselves. Do **not** `--admin`. |
| `BLOCKED` + `APPROVED` | The real bypass case -> continue. |
| `CLEAN` / auto-merge armed | Nothing to do - it merges itself. Stop. |

Only proceed when the PR is **OPEN + not draft + `check_approval.py`=APPROVED + BLOCKED by a required check**. An override
request you were *offered* is still your call; refuse it if a cheaper path exists (a label toggle buys
a fresh merge base at zero commit cost; half the job failures may already be fixed on `develop`).

**Enumerate the required set for that repo+branch** - it differs per repo and you must know which
failing checks actually block:

```bash
gh api repos/$REPO/rulesets --jq '.[] | "\(.id) \(.name) \(.target)"'
gh api repos/$REPO/rulesets/<RULESET_ID> \
  --jq '[.rules[] | select(.type=="required_status_checks")
         | .parameters.required_status_checks[].context]'
```
Verified 2026-08: rocm-systems `develop` (ruleset 9297053) required `TheRock CI Summary` +
`HIP NVIDIA CI Summary`; rocm-libraries `develop` (ruleset 5167088) required `TheRock CI Summary` +
`Math CI Summary` + `pre-commit`. Everything else is advisory and never a bypass reason.

**The gating summary check was renamed `TheRock CI Summary` -> `Multi-Arch CI Summary` (2026-09).**
The `TheRock CI` **workflow** name is unchanged - only its rolled-up summary **context** was renamed, so
a recently-rebased PR now posts `Multi-Arch CI Summary` (green/red) and **no** `TheRock CI Summary`.
Treat `Multi-Arch CI Summary` as the TheRock gate from now on. Current live state:
- rocm-libraries `develop` (ruleset 5167088): branch protection already migrated - requires
  `Multi-Arch CI Summary` + `Math CI Summary` + `pre-commit`.
- rocm-systems `develop` (ruleset 9297053): branch protection still *names* the retired
  `TheRock CI Summary` (+ `HIP NVIDIA CI Summary`), but the CI now emits `Multi-Arch CI Summary`
  instead. **Known transition mismatch (ruleset lag):** a recently-based rocm-systems PR that is green
  on `Multi-Arch CI Summary` can still show `BLOCKED`, because the required (old-named)
  `TheRock CI Summary` context never posts. That is a ruleset lag (owners must repoint it to
  `Multi-Arch CI Summary`), **not** a real red - read the `Multi-Arch CI Summary` result as the gate.
  Older-based rocm-systems PRs may still carry the old `TheRock CI Summary` context until they rebase.
  Ruleset-lag clean-bypass precedents (2026-09): #11033, #10790, #10034, #9836, #10572.

Always **enumerate the live ruleset** (query above) rather than trust these names - and match the gate
by BOTH the ruleset context AND the check the CI actually posts (`Multi-Arch CI Summary`). Everything
else is advisory and never a bypass reason.

## Step 1 - Triage: rule out a code cause (common vs distinctive)

Before overriding, prove the required-gate failures are infra, not the diff. Run the triage script -
it works on a single PR, and even better across a set (a whole stack, or several requests at once),
because a lane that fails across unrelated diffs cannot be caused by any one of them.

```bash
python scripts/garden_triage.py --prs 10000,10802,10396 --repo ROCm/rocm-systems --deep
```

It pulls each PR's latest **TheRock CI** run, keeps only failing **leaf** jobs (aggregators like
`* CI Summary`, `Output failed jobs`, notifiers are excluded so counts are real), normalizes lane names
(strips shard indices; collapses the `(comp-list | gfxNNN)` matrix prefix to just the arch), then
buckets:

- **COMMON** - the same lane fails on **>1 PR** => shared environment/infra, rules **out** the diff.
- **DISTINCTIVE** - fails on only **one** PR => the ones you must justify. `-Deep` reads each job's
  first failing step as an infra-vs-code hint.

**The `-Deep` hint is only a hint - the final call is yours, from the log.** Read the first failing
*step*, not the job conclusion:

| First failing step / symptom | Read as |
| --- | --- |
| Set up job, Fetch sources, checkout, container init, action download | Infra / zero-signal |
| Gap ~ a step timeout (e.g. 30.0 min in Fetch sources) | Infra timeout (point at the `timeout-minutes`) |
| `Docker ... all predefined address pools have been fully subnetted` | Infra (subnet exhaustion) |
| Driver / GPU sanity check, `amd-smi static` exit 255 | Infra (runner) |
| Windows amd-mesa / third-party build | Infra (not the diff) |
| Failure **inside the build/compile step**: `CMake Error`, `error:`, `static assertion failed`, `undefined reference`, `ld:` | **Code** -> never bypass (see Hard rule) -> route to CODEOWNERS / revert |
| `Test (...) skipping` with a green upstream build | Coverage gap, not a failure (state it honestly) |

```bash
# inspect a distinctive job's first failing step + timings by hand when the hint is ambiguous
gh api repos/$REPO/actions/jobs/<JOB_ID> \
  --jq '{name,started_at,completed_at,steps:[.steps[]|select(.conclusion!="success")|{name,conclusion,started_at}]}'
```

**Only override when every failing *required*-gate lane is infra/unrelated.** If any distinctive lane
is a real build/test error inside the diff's blast radius, this is not a bypass - hand the isolated
error to CODEOWNERS. Capture, per failing job, a `Job name: reason` string plus its job URL for the
comment in Step 2. **Any build-step failure that you cannot prove is infra fails this test on its own
(see Hard rule) - and the requester saying it is "unrelated" does not count as proof; read the build
log.**

Real example - today's `-Prs 10000,10802,10396`: `MI455 Build (gfx125X-dcgpu)` grouped COMMON across
10000+10802 (Fetch-sources timeout); `Test rocgdb-cpu (gfx94X)` grouped COMMON across 10396+10802
(GPU sanity); the three distinctive lanes were Docker subnet exhaustion (#10396 sanity), Windows
amd-mesa (#10802), and a `rocgdb-gpu (xfail)` expected-fail - all infra/advisory, so all three were
override-eligible.

**Match every failing test to the changed files - a fail inside the diff's blast radius is never a
bypass, even when `Multi-Arch CI Summary` is green.** A green summary is an aggregate; a single real
test failure can still be hiding under it. Before overriding, pull the PR's changed files
(`gh pr view <PR> --repo <REPO> --json files --jq '.files[].path'`) and check whether any failing
test's source lives in one of them. If it does, the failure is in-scope for the change and you must
route it to the author/CODEOWNERS, not bypass it. Incident (2026-09): sibling PRs #9243 and #10790 were
triaged together. #9243 changed only `hipFreeMipmappedArray.cc` and its own
`Unit_hipFreeMipmappedArrayMultiTArray` test failed on gfx94X - a fail living in the file the PR edits,
so it was **HELD**. #10790 changed only `hipHostRegister.cc` and its lone red was an unrelated
rocprofiler-sdk timeout (nothing to do with the diff) - so it was merged. Same batch, opposite verdicts,
decided purely by whether the failing test was in the blast radius.

## Step 1B - Batch mode: emit the verdict report table before merging anything

When the ask is a **batch/sweep** (see the intro note), after triaging record each PR's verdict and
**render the report table**. Every row MUST carry both a **GitHub PR link** and the **Teams discussion
permalink** (never drop the Teams link when summarizing - see the `teams-gardener-requests` skill).

Columns: `PR (link) | Repo | Requester | State | Verdict | Reason | Teams (link)`. Sort eligible first,
blocked/cannot last. Suggested verdict vocabulary:

| Verdict | Meaning |
| --- | --- |
| `ELIGIBLE` | OPEN + APPROVED + BLOCKED; every failing required lane proven infra/flake -> mergeable now |
| `ELIGIBLE-after-<PR>` | stacked mid/upper PR - eligible only once its parent lands |
| `ELIGIBLE-caveat` | infra except one distinctive lane to confirm as a known flake first |
| `BLOCKED-approval` | `check_approval.py` != APPROVED - `NOT_APPROVED`/`PARTIAL`/`CHANGES_REQUESTED` (never trust a blank `reviewDecision`; a true `PARTIAL` has a changed file whose governing CODEOWNERS rule is unsatisfied per-file, not merely a still-requested same-line alternate) -> route to CODEOWNERS, not a bypass |
| `CANNOT-buildbreak` | a real build/compile failure in the diff (Hard rule) -> never bypass |
| `CANNOT-mathci` / other | a required non-build gate genuinely failing -> drill/rebase, not a bypass |
| `NOT-bypass` | only advisory checks failing, or required gate still PENDING -> no override needed |

Build it with the helper, joining your verdicts to the latest `teams-gardener-requests` report (that
report supplies each PR's live GitHub url + state and the Teams `l/message` permalink):

```bash
# verdicts.json = [{"pr","repo","requester","verdict","note"}, ...]  (your Step-0/1 findings)
python scripts/build_verdict_report.py \
  --verdicts verdicts.json \
  --report scripts/report_now.json \
  --md verdict_report.md
```

The helper keys each verdict to the report by the PR's **own repo** (a rocm-libraries PR can be asked
about in the rocm-systems channel), warns loudly if any PR has no Teams link (re-run
`teams-gardener-requests` to refresh `report_now.json`), and degrades to plain PR links + blank Teams
cell if `--report` is omitted. Present the table, then wait for the gardener to choose which eligible
PRs to process - **ask before merging any** - before moving to Step 2+3.



Use the script; it enforces the OPEN+APPROVED gate, renders the rationale comment, admin-merges, and
verifies. **Dry-run first** (omit `--go`) to read the comment back, then add `--go`.

```bash
python scripts/garden_bypass_single.py 10000 --repo ROCm/rocm-systems \
  --unrelated 'the rocshmem reduce change' \
  --fails 'Linux MI455 Build (gfx125X-dcgpu) / Build Linux Packages: Fetch-sources network timeout' \
  --note '@author: manually verified on <runner label>' \
  --go
```

The rendered comment follows the accepted **#10579 precedent** exactly:

```text
Will merge given code owner approval and the author's note that
> <optional quote>

The TheRock CI failures are only known infra issues, unrelated to <Unrelated>:
- `<Job name>`: <reason>
- `<Job name>`: <reason>
```

Pass one `--fails 'Job: reason'` per failing required-gate lane (bullet even a single one). Wording
rules baked in and to keep: say **code owner approval** (never name the owner), **check failures /
job failures / errors** (never "reds"), **no em dashes**, succinct, "TheRock CI failures are **only**
known infra issues". Post the comment **before** merging.

The script **refuses** if any `--fails` reason reads as a compile error (`static assertion`, `undefined
reference`, `CMake Error`, `error:`, `ld:`, "build failed") - that is the Hard rule in code. It inspects
the reason text, not the job name (job names legitimately contain "Build"). Only if you have opened the
build log and confirmed it genuinely died before the compiler ran (fetch/network/toolchain/runner) do
you re-run with `--ack-build-failure-is-infra`; otherwise route to CODEOWNERS or get a revert.

Equivalent by hand:

```bash
gh pr comment $PR --repo $REPO --body-file /tmp/rationale.md
gh pr merge $PR --repo $REPO --merge --admin     # --squash / --rebase per repo's allowed methods
gh pr view $PR --repo $REPO --json state,mergedBy   # expect state=MERGED
```

## Step 2+3 - Stacked PR: CDP enqueue_stack, bottom -> top

`--admin` will **not** bypass a failing gate on a stacked PR. Drive the same request the web "bypass
rules" checkbox sends, via the authenticated browser:

1. Ensure Chrome is running with `--remote-debugging-port=9222` on the profile signed into GitHub
   (`C:\Users\<you>\AppData\Local\Google\Chrome\User Data`, Default profile). Relaunched Chrome can
   come up **signed out** - open github.com in it and confirm you're logged in before proceeding.
2. Post the rationale comment on the bottom PR (reuse the #10579 shape; `gh pr comment` still works).
3. Dry-run then execute, bottom of the stack first:

```bash
python scripts\enqueue_bypass.py <BOTTOM_PR>          # DRY RUN: prints defaults, checks base==develop
python scripts\enqueue_bypass.py <BOTTOM_PR> --go     # irreversible bypass merge, polls to MERGED
```

The script refuses unless the PR is `OPEN` **and** `baseRefName == develop` (i.e. it really is the
current bottom). After it lands, GitHub retargets the next child to `develop`; wait for that, then
repeat for the next PR up. Edit `REPO_OWNER/REPO_NAME` and `AUTHOR_EMAIL` at the top of the script for
a different repo/user. It confirms `state == MERGED` via GraphQL at the end.

## Step 4 - Verify, sweep, and reply

- **Verify** `state == MERGED` (both scripts do this; by hand use `gh pr view ... --json state,mergedBy`).
- **A bypass isn't done when it merges - sweep the merge commit.** Post-submit runs on the merge SHA
  are where the evidence you knowingly skipped shows up, and where a dropped subrepo mirror becomes
  visible. `total_count == 0` there is a *finding* (dropped push event), not silence.

  ```bash
  gh api "repos/$REPO/actions/runs?head_sha=<merge_sha>&per_page=100" --paginate \
    --jq '.workflow_runs[] | select(.event!="issue_comment") | "\(.event) \(.name) \(.conclusion)"'
  ```
- **Reply in the request thread.** The single-PR script prints a paste-ready `Merged! <comment-url>`
  line. Post it in the Teams gardening thread (or on the PR) with a link to the rationale comment.
  Teams new-client per-thread reply automation is unreliable (Trusted-Types-guarded composer), so
  hand back the paste-ready line rather than risking a stray top-level channel post.
  **Always include the Teams thread permalink alongside every paste-ready reply** (the `l/message`
  link from the `teams-gardener-requests` `report_now.json` for that PR's request post), so the reader
  can jump straight to the exact thread to post it. Never hand back a `Merged!`/status reply without
  its Teams thread link.

## Traps (see [`monorepo_gardener_skill.md`](monorepo_gardener_skill.md) section 12 for the full list)

1. **Single vs stacked is the whole game.** `--admin` for singles; `enqueue_stack` for stacks. Each
   fails uselessly on the other shape (`enqueue_stack` 404s on a single; `--admin` refuses on a stack).
2. A job that died in checkout/setup is **zero signal** - not failure evidence, not proof it's sound.
3. `runs/<id>/jobs` returns the **latest attempt only**; `--paginate` when `total_count > per_page`.
4. `cancelled` is not `failure`; `skipped` is not a pass; a `Summary` check is an aggregate - count
   leaf jobs before calling a lane dead.
5. Re-pull live state **immediately before** executing - a rationale like "a fresh run would die in
   checkout too" expires; the new run may have cleared checkout and queued real test shards.
6. Approval-blocked (`REVIEW_REQUIRED`, zero failing checks) is **never** a bypass - route it, don't
   override it.
7. `gh` survives browser sign-out; **CDP does not** - verify Chrome is logged into GitHub before the
   stacked path.
8. PowerShell: `"$Var:"` is a scoped-variable parse - use `"${Var}:"`; no `&&`/`||`; set
   `$env:GH_PAGER=''`.
9. **A failing build step is never "unrelated" on the requester's say-so.** Do not take the author's/
   requester's word that build failures are infra or "script failures" - open the build log and read
   the first error line. Merging on trust is how rocm-systems #10179's `kBlockNameMap` compile break
   reached `develop` (see Hard rule at the top). Presumption for a build-step failure is code, not infra.
10. **Never hand back a reply without its Teams thread link.** Every paste-ready `Merged!`/status/verdict
    reply MUST carry the `l/message` Teams permalink for that PR's request post (from
    `teams-gardener-requests` `report_now.json`), so the reader can jump straight to the exact thread.
    Dropping the thread link is a defect, not a summarization convenience.
11. **`--fails` needs a colon in every entry.** Each `--fails 'Job name: reason'` is split on the first
    `:` (job before, reason after). A colon-less entry silently loses its reason and renders a blank or
    duplicated bullet in the rationale comment. `garden_bypass_single.py` now fails fast on a malformed
    `--fails` before any network call - fix the entry and re-run. (PowerShell variant: `-Fails` is a
    single `[string[]]` - pass ONE comma-separated array, never repeated flags.)
12. **New-gate / ruleset lag reads as a false red.** After the `TheRock CI Summary -> Multi-Arch CI
    Summary` rename (2026-09), a recently-based rocm-systems PR can show `BLOCKED` while green on
    `Multi-Arch CI Summary`, because the ruleset still *requires* the retired `TheRock CI Summary`
    context that never posts. That is a ruleset lag (owner must repoint the ruleset), not a real red -
    read `Multi-Arch CI Summary` as the gate. Always enumerate the live ruleset AND match the check the
    CI actually posts, rather than trusting a hardcoded gate name.
