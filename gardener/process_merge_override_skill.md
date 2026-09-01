---
name: process-merge-override
description: Process a merge-override / bypass-merge request for one ROCm/rocm-systems or ROCm/rocm-libraries PR whose only required-gate check failures are known infra flakes. Verifies the four bypass preconditions, runs the common-vs-distinctive failure triage to rule out code causes, posts a #10579-style rationale comment, then merges past the failing required gate (single PR via `gh pr merge --admin`; stacked PR via the CDP `enqueue_stack` driver), verifies MERGED, and hands back a Teams "Merged!" reply that always includes the Teams thread permalink. When the ask covers several PRs (a stack, a list, or a "process the open override requests" sweep), it first emits a verdict report table — one row per open PR with the GitHub PR link, the Teams discussion permalink, and a can/cannot verdict — and asks which to merge before executing. Use when a gardener is asked to force-merge / override / bypass a blocked PR. Companion to monorepo-gardener.
---

# Skill: Process a merge-override request

For the **ROCm/rocm-systems** and **ROCm/rocm-libraries** gardener rotation, when someone asks you to
**override / force-merge / bypass** a PR that is `BLOCKED` because a *required* gate is failing on what
they believe are known infra flakes (e.g. in the gardening Teams channel or on the PR thread).

This is the **execution** counterpart to [`monorepo_gardener_skill.md`](monorepo_gardener_skill.md): that
skill classifies a blocked PR; this one takes the decision-to-override through to a verified merge and
a posted rationale. The normative policy is each repo's own `docs/gardening.md` and wins over anything
here. **You are a facilitator for CI/infra triage, not the component code owner** — you sign off on the
infra classification, never on numerics, performance, or component-code correctness.

Scripts referenced below live in `scripts/` next to this file. All are dry-run by default.

## When asked to process a *batch* (several PRs, "process these", or a fresh sweep): report first

If the ask covers **more than one** PR — a stack, a list, or a "process the open override
requests" sweep — do **not** start merging. First triage every PR (Steps 0–1) and emit the
**verdict report table** (Step 1B): one row per OPEN request PR with its **GitHub PR link**, the
**Teams discussion permalink**, and a can/cannot **verdict + reason**. Present that table and let the
gardener pick which eligible PRs to merge before you execute anything. A single named PR
("/process-merge-override 10487") skips straight to Step 0 for that PR.

## Hard rule — a failing BUILD/COMPILE step is never bypass-eligible unless it is definitively infra

This overrides everything below. If a *required*-gate failure happened **inside the build/compile
step**, you may not override it unless you have proven from the log that it is an infrastructure
failure (fetch/clone/network, toolchain or container provisioning, runner death — i.e. something that
died **before the compiler ran**). A compiler/linker/`static_assert` error **is the PR's code failing
to build** and blocks the merge, full stop — route it to CODEOWNERS or get it reverted; do not bypass.

- **Never take the requester's or author's word that failures are "unrelated" / "just script
  failures."** That is a claim to verify, not evidence. Open the actual build log and read the first
  error line yourself. A green "trust me" from the person asking you to merge is worth nothing against
  a failing build step.
- **Build-step failure ⇒ presumed code-caused.** The burden is on proving infra, not on proving code.
  If you cannot definitively show it is infra, treat it as code and refuse the override.
- Distinguish from the log, not the conclusion: `error:`, `static assertion failed`, `undefined
  reference`, `ld: `, a `CMake Error` at the compile/link stage = **code**. "Fetch sources" timeout,
  clone/network error, container/toolchain provisioning, runner offline = **infra** (and only these are
  bypass-eligible for a build step).

**Incident this rule comes from (rocm-systems #10179, 2026-08).** A gardener was asked to merge an
approved PR with "a few CI failures"; asked "these are unrelated right?", the author answered "those
are some script run failures", and it was merged on that word. The failure was in fact a real compile
break — a `kBlockNameMap` `static_assert` in `projects/rdc/tests/rdc_tests/test_common.cc` tripped by
the PR's amdsmi GPU-block enum expansion. It landed on `develop`, broke the RDC build for **everyone**
(and later surfaced as the "develop-level" `kBlockNameMap` failure in other triage), and had to be
reverted (#10947) with a tracking issue filed. The owners' explicit correction: *"please do not take
developers' word for build compilation issues; CI failures for build should never be treated as
un-related."* Had this rule been applied, #10179 would not have been overridden.

## The one thing that decides everything: single vs stacked

The PR's shape picks the merge tool. Get this wrong and the merge silently no-ops or 404s.

| PR shape | How to detect | Bypass tool | Auth |
| --- | --- | --- | --- |
| **Single** (base is `develop` **and** no child PRs) | `baseRefName == develop` **and** no open PR has `baseRefName == <this PR's headRefName>` | `gh pr merge <PR> --merge --admin` | gh token, **no browser** |
| **Stacked** (base is another PR's branch, **or** it has children on its head) | `baseRefName` is some `feature/...` branch, **or** another open PR targets its head | `enqueue_bypass.py <PR> --go` (CDP `enqueue_stack`) | authenticated Chrome on `:9222` |

```bash
gh pr view <PR> --repo <REPO> --json baseRefName,headRefName,state,mergeStateStatus,reviewDecision,isDraft
# base==develop is necessary but NOT sufficient — also confirm nothing is stacked ON it:
gh pr list --repo <REPO> --base <this PR's headRefName> --state open --json number
```

> **`base == develop` is not enough.** If any open PR is based on *this* PR's head branch, GitHub
> treats it as a **stack** and `--admin` / merge-async is refused with *"part of a stack and must be
> merged using the asynchronous merge REST API"* — even though the base is `develop`. Always run the
> children check above; only a PR that is base==develop **and** childless is a true single.

> **Endpoint drift (2026-09):** the CDP `enqueue_stack` **write** endpoint has returned **401** even
> with a valid verified-fetch nonce (verified-fetch *reads* — `page_data/merge_box` GET — still 200,
> confirming the nonce/headers are fine). GitHub moved/renamed the stacked-merge write path. When this
> happens, `enqueue_bypass.py` cannot land the merge; re-capture the current request the web "bypass
> rules" merge issues (Network log while a human clicks it) and update the driver's URL/payload. Do
> **not** force the merge through fragile click-automation — the merge is irreversible.

- On a **single** PR, `--admin` merges straight past a failing required gate. `enqueue_stack` **404s**
  on a single PR — do not use it there.
- On a **stacked** PR, `--admin` / merge-async is refused with *"Required status check … is failing"*.
  You must drive the web "bypass rules" path via `enqueue_bypass.py`, merging **bottom → top**, one PR
  at a time, re-pointing each child's base to `develop` as its parent lands.

`gh` (token) survives a browser sign-out; **CDP does not**. If you'll need the stacked path, confirm
Chrome is up and signed into GitHub first (see §Stacked execution).

## Step 0 — Confirm this is actually a bypass case (don't open a log yet)

```bash
REPO=ROCm/rocm-systems   # or ROCm/rocm-libraries
PR=<number>
gh pr view $PR --repo $REPO --json state,mergeStateStatus,reviewDecision,isDraft,baseRefName,autoMergeRequest
```

> **Do NOT gate on `reviewDecision` alone — it lies.** GitHub returns an **empty/null**
> `reviewDecision` even when code owners **have** approved (common when CODEOWNERS spans several owner
> teams: some approve while others stay auto-requested). Treating empty as "not approved" hides real
> approvals and mislabels the PR. Always resolve the true state with the helper, which reads
> `latestOpinionatedReviews` + outstanding codeowner `reviewRequests`:
> ```bash
> python scripts\check_approval.py $PR --repo $REPO   # -> APPROVED | PARTIAL | NOT_APPROVED | CHANGES_REQUESTED
> ```
> | check_approval verdict | Meaning | Bypass on review axis? |
> | --- | --- | --- |
> | `APPROVED` | all required owners satisfied, no changes requested | eligible → continue |
> | `PARTIAL` | some owners approved, **other required codeowner teams still outstanding** | **No** — route the remaining owners |
> | `NOT_APPROVED` | `REVIEW_REQUIRED` or no standing approval | **No** — route to CODEOWNERS |
> | `CHANGES_REQUESTED` | a reviewer's latest stance is changes-requested | **No** — hard stop |
>
> A gardener bypass is for known-infra/flaky **CI**, **never** for unmet code review. Only `APPROVED`
> clears the review axis; everything else routes to CODEOWNERS regardless of the CI state.

| `mergeStateStatus` / approval (via `check_approval.py`, not raw `reviewDecision`) | Verdict |
| --- | --- |
| `BLOCKED` + `NOT_APPROVED`/`PARTIAL`/`CHANGES_REQUESTED` | Review-blocked, **not** a bypass. Route to CODEOWNERS (name the outstanding owners). Stop. |
| `UNSTABLE` + `APPROVED` | Every failing check is advisory — author squashes it themselves. Do **not** `--admin`. |
| `BLOCKED` + `APPROVED` | The real bypass case → continue. |
| `CLEAN` / auto-merge armed | Nothing to do — it merges itself. Stop. |

Only proceed when the PR is **OPEN + not draft + `check_approval.py`=APPROVED + BLOCKED by a required check**. An override
request you were *offered* is still your call; refuse it if a cheaper path exists (a label toggle buys
a fresh merge base at zero commit cost; half the job failures may already be fixed on `develop`).

**Enumerate the required set for that repo+branch** — it differs per repo and you must know which
failing checks actually block:

```bash
gh api repos/$REPO/rulesets --jq '.[] | "\(.id) \(.name) \(.target)"'
gh api repos/$REPO/rulesets/<RULESET_ID> \
  --jq '[.rules[] | select(.type=="required_status_checks")
         | .parameters.required_status_checks[].context]'
```
Verified 2026-08: rocm-systems `develop` requires only `TheRock CI Summary` + `HIP NVIDIA CI Summary`;
rocm-libraries `develop` requires `TheRock CI Summary` + `Math CI Summary` + `pre-commit`. Everything
else is advisory and never a bypass reason.

## Step 1 — Triage: rule out a code cause (common vs distinctive)

Before overriding, prove the required-gate failures are infra, not the diff. Run the triage script —
it works on a single PR, and even better across a set (a whole stack, or several requests at once),
because a lane that fails across unrelated diffs cannot be caused by any one of them.

```bash
python scripts/garden_triage.py --prs 10000,10802,10396 --repo ROCm/rocm-systems --deep
```

It pulls each PR's latest **TheRock CI** run, keeps only failing **leaf** jobs (aggregators like
`* CI Summary`, `Output failed jobs`, notifiers are excluded so counts are real), normalizes lane names
(strips shard indices; collapses the `(comp-list | gfxNNN)` matrix prefix to just the arch), then
buckets:

- **COMMON** — the same lane fails on **>1 PR** ⇒ shared environment/infra, rules **out** the diff.
- **DISTINCTIVE** — fails on only **one** PR ⇒ the ones you must justify. `-Deep` reads each job's
  first failing step as an infra-vs-code hint.

**The `-Deep` hint is only a hint — the final call is yours, from the log.** Read the first failing
*step*, not the job conclusion:

| First failing step / symptom | Read as |
| --- | --- |
| Set up job, Fetch sources, checkout, container init, action download | Infra / zero-signal |
| Gap ≈ a step timeout (e.g. 30.0 min in Fetch sources) | Infra timeout (point at the `timeout-minutes`) |
| `Docker … all predefined address pools have been fully subnetted` | Infra (subnet exhaustion) |
| Driver / GPU sanity check, `amd-smi static` exit 255 | Infra (runner) |
| Windows amd-mesa / third-party build | Infra (not the diff) |
| Failure **inside the build/compile step**: `CMake Error`, `error:`, `static assertion failed`, `undefined reference`, `ld:` | **Code** → never bypass (see Hard rule) → route to CODEOWNERS / revert |
| `Test (…) skipping` with a green upstream build | Coverage gap, not a failure (state it honestly) |

```bash
# inspect a distinctive job's first failing step + timings by hand when the hint is ambiguous
gh api repos/$REPO/actions/jobs/<JOB_ID> \
  --jq '{name,started_at,completed_at,steps:[.steps[]|select(.conclusion!="success")|{name,conclusion,started_at}]}'
```

**Only override when every failing *required*-gate lane is infra/unrelated.** If any distinctive lane
is a real build/test error inside the diff's blast radius, this is not a bypass — hand the isolated
error to CODEOWNERS. Capture, per failing job, a `Job name: reason` string plus its job URL for the
comment in Step 2. **Any build-step failure that you cannot prove is infra fails this test on its own
(see Hard rule) — and the requester saying it is "unrelated" does not count as proof; read the build
log.**

Real example — today's `-Prs 10000,10802,10396`: `MI455 Build (gfx125X-dcgpu)` grouped COMMON across
10000+10802 (Fetch-sources timeout); `Test rocgdb-cpu (gfx94X)` grouped COMMON across 10396+10802
(GPU sanity); the three distinctive lanes were Docker subnet exhaustion (#10396 sanity), Windows
amd-mesa (#10802), and a `rocgdb-gpu (xfail)` expected-fail — all infra/advisory, so all three were
override-eligible.

## Step 1B — Batch mode: emit the verdict report table before merging anything

When the ask is a **batch/sweep** (see the intro note), after triaging record each PR's verdict and
**render the report table**. Every row MUST carry both a **GitHub PR link** and the **Teams discussion
permalink** (never drop the Teams link when summarizing — see the `teams-gardener-requests` skill).

Columns: `PR (link) | Repo | Requester | State | Verdict | Reason | Teams (link)`. Sort eligible first,
blocked/cannot last. Suggested verdict vocabulary:

| Verdict | Meaning |
| --- | --- |
| `ELIGIBLE` | OPEN + APPROVED + BLOCKED; every failing required lane proven infra/flake → mergeable now |
| `ELIGIBLE-after-<PR>` | stacked mid/upper PR — eligible only once its parent lands |
| `ELIGIBLE-caveat` | infra except one distinctive lane to confirm as a known flake first |
| `BLOCKED-approval` | `check_approval.py` ≠ APPROVED — `NOT_APPROVED`/`PARTIAL`/`CHANGES_REQUESTED` (never trust a blank `reviewDecision`; a `PARTIAL` still has outstanding codeowner teams) → route to CODEOWNERS, not a bypass |
| `CANNOT-buildbreak` | a real build/compile failure in the diff (Hard rule) → never bypass |
| `CANNOT-mathci` / other | a required non-build gate genuinely failing → drill/rebase, not a bypass |
| `NOT-bypass` | only advisory checks failing, or required gate still PENDING → no override needed |

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
PRs to process — **ask before merging any** — before moving to Step 2+3.



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
reference`, `CMake Error`, `error:`, `ld:`, "build failed") — that is the Hard rule in code. It inspects
the reason text, not the job name (job names legitimately contain "Build"). Only if you have opened the
build log and confirmed it genuinely died before the compiler ran (fetch/network/toolchain/runner) do
you re-run with `--ack-build-failure-is-infra`; otherwise route to CODEOWNERS or get a revert.

Equivalent by hand:

```bash
gh pr comment $PR --repo $REPO --body-file /tmp/rationale.md
gh pr merge $PR --repo $REPO --merge --admin     # --squash / --rebase per repo's allowed methods
gh pr view $PR --repo $REPO --json state,mergedBy   # expect state=MERGED
```

## Step 2+3 — Stacked PR: CDP enqueue_stack, bottom → top

`--admin` will **not** bypass a failing gate on a stacked PR. Drive the same request the web "bypass
rules" checkbox sends, via the authenticated browser:

1. Ensure Chrome is running with `--remote-debugging-port=9222` on the profile signed into GitHub
   (`C:\Users\<you>\AppData\Local\Google\Chrome\User Data`, Default profile). Relaunched Chrome can
   come up **signed out** — open github.com in it and confirm you're logged in before proceeding.
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

## Step 4 — Verify, sweep, and reply

- **Verify** `state == MERGED` (both scripts do this; by hand use `gh pr view … --json state,mergedBy`).
- **A bypass isn't done when it merges — sweep the merge commit.** Post-submit runs on the merge SHA
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

## Traps (see [`monorepo_gardener_skill.md`](monorepo_gardener_skill.md) §12 for the full list)

1. **Single vs stacked is the whole game.** `--admin` for singles; `enqueue_stack` for stacks. Each
   fails uselessly on the other shape (`enqueue_stack` 404s on a single; `--admin` refuses on a stack).
2. A job that died in checkout/setup is **zero signal** — not failure evidence, not proof it's sound.
3. `runs/<id>/jobs` returns the **latest attempt only**; `--paginate` when `total_count > per_page`.
4. `cancelled` is not `failure`; `skipped` is not a pass; a `Summary` check is an aggregate — count
   leaf jobs before calling a lane dead.
5. Re-pull live state **immediately before** executing — a rationale like "a fresh run would die in
   checkout too" expires; the new run may have cleared checkout and queued real test shards.
6. Approval-blocked (`REVIEW_REQUIRED`, zero failing checks) is **never** a bypass — route it, don't
   override it.
7. `gh` survives browser sign-out; **CDP does not** — verify Chrome is logged into GitHub before the
   stacked path.
8. PowerShell: `"$Var:"` is a scoped-variable parse — use `"${Var}:"`; no `&&`/`||`; set
   `$env:GH_PAGER=''`.
9. **A failing build step is never "unrelated" on the requester's say-so.** Do not take the author's/
   requester's word that build failures are infra or "script failures" — open the build log and read
   the first error line. Merging on trust is how rocm-systems #10179's `kBlockNameMap` compile break
   reached `develop` (see Hard rule at the top). Presumption for a build-step failure is code, not infra.
10. **Never hand back a reply without its Teams thread link.** Every paste-ready `Merged!`/status/verdict
    reply MUST carry the `l/message` Teams permalink for that PR's request post (from
    `teams-gardener-requests` `report_now.json`), so the reader can jump straight to the exact thread.
    Dropping the thread link is a defect, not a summarization convenience.
