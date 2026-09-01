# Example: a merge-override rotation, end to end (week 36, Aug 24–31 2026)

A full **rocm-systems / rocm-libraries** gardener rotation seen from the override desk: how the
requests were acquired, triaged, and decided, what was merged vs refused, and — most usefully — the
**two build-break mistakes** that reshaped the [`process_merge_override_skill.md`](../../process_merge_override_skill.md)
Hard rule. This is the case study behind that skill's build-guard.

It exercises the whole gardener loop:

| Skill / command | Role in this rotation |
| --- | --- |
| [`teams_gardener_requests_skill.md`](../../teams_gardener_requests_skill.md) (`/tgr`) | **Acquire** — pull every merge/override/help ask from both Gardening channels into a table with Teams permalinks |
| [`monorepo_gardener_skill.md`](../../monorepo_gardener_skill.md) (`/gr`) | **Triage** — classify each blocked PR's reds into infra / code / advisory |
| [`process_merge_override_skill.md`](../../process_merge_override_skill.md) (`/pmo`) | **Decide + execute** — verify preconditions, prove infra, merge past the required gate, sweep, reply |

## The loop, as an outline

1. **Acquire the requests.** Run `/tgr` (`pull_gardener_requests.py --sync --hours 48`) against the
   authenticated Teams CDP browser. It reads the Teams IndexedDB cache (not the DOM) and emits one row
   per request post with the referenced PRs, live `gh` state, and a `l/message` **Teams permalink**.
   Keep that permalink on every row you ever re-present — it is how anyone jumps back to the ask.
   - The classifier decides what counts as a merge/override/help ask. This rotation it was **widened**
     (see "Skill changes" below) after it missed several real asks phrased as "help **merging** this"
     or "the failures are **unrelated**".
2. **Enumerate the required set per repo.** `rocm-systems develop` requires only `TheRock CI Summary`
   + `HIP NVIDIA CI Summary`; `rocm-libraries develop` requires `TheRock CI Summary` + `Math CI
   Summary` + `pre-commit`. Everything else (Core, Code Coverage, `therock-pr-bot`, component CIs) is
   **advisory** and never a bypass reason. Confirm with the `rulesets` API, do not assume.
3. **Resolve approval honestly.** `check_approval.py` reads `latestOpinionatedReviews` + outstanding
   codeowner `reviewRequests`. A blank `reviewDecision` is **not** "unapproved" — it usually means
   CODEOWNERS spans several owner teams and some are still auto-requested. Only `APPROVED` clears the
   review axis; `PARTIAL` / `NOT_APPROVED` / `CHANGES_REQUESTED` route to CODEOWNERS. A gardener bypass
   is for known-infra/flaky **CI only**, never for unmet code review.
4. **Triage the reds — infra vs code.** Use common-vs-distinctive (`garden_triage.ps1 -Deep`): a lane
   that fails across *unrelated* PRs is shared infra; a lane that passes on the mainstream arch
   (gfx94X/MI300) and only fails on a new/rare lane (gfx1250/MI455) is a lane/arch artifact, not the
   diff. **Read the first failing *step*, not the job conclusion.**
5. **Apply the Hard rule to build steps.** A failure *inside the build/compile step* is presumed
   code-caused and is bypass-ineligible unless the log proves it died before the compiler ran
   (fetch/network/toolchain/runner). This is the rule the two mistakes below created.
6. **Pick the tool by shape.** base==develop **and childless** ⇒ single ⇒ `garden_bypass_single.ps1`
   (`--admin`, gh token). Base is another PR's branch **or** it has children on its head ⇒ stacked ⇒
   `enqueue_bypass.py` (CDP `enqueue_stack`), merged bottom → top.
7. **Prefer the cheaper path.** If the reds are already fixed on `develop`, a re-run / rebase clears
   them at zero commit cost — a bypass is then neither needed nor allowed.
8. **Execute, sweep, reply.** Dry-run, post the `#10579`-shape rationale, merge, verify `MERGED`,
   then sweep the merge SHA (a merge commit with **zero** push runs is a dropped-event *finding*).
   Hand back the paste-ready `Merged! <comment-url>` line **with the Teams thread permalink**.

## What this rotation decided

Merged past a failing required gate (all verified infra/flake, approved, swept clean):

| PR | Shape | Why it was eligible |
| --- | --- | --- |
| `rocm-systems#9031` | single | Windows gfx1151 build = known `win_flex`/amd-mesa infra; tests common/infra |
| `rocm-systems#9584` | single | hip-tests pass on MI300; MI455 gfx1250 invalid-image + HRR flake + Docker infra + Windows flex |
| `rocm-systems#9696` | single | required gates green; only advisory `Core`/`Code Coverage` mi325 red |
| `rocm-systems#10083`/`#10084` | stacked | cuid tooling; CDP `enqueue_stack` bottom→top; advisory-only reds |
| `rocm-systems#10653` | single | flaky-test disable |
| `rocm-systems#10803` | single | build green; only `rocgdb-cpu` Driver/GPU-sanity infra failure, unrelated to the diff |
| `rocm-systems#10953` | single | build clean; rocprofiler-sdk timeout + container-init infra |
| `rocm-libraries#10311` | single | merged after its required Math CI finished green |

Refused (correctly not bypassed):

| PR | Verdict | Reason |
| --- | --- | --- |
| `rocm-systems#8690` | re-run/rebase | stale `kBlockNameMap` build break (fixed on develop); also stacked |
| `rocm-systems#9431` | approval | `REVIEW_REQUIRED` — route to CODEOWNERS |
| `rocm-systems#9738` | build break | real Linux compile break + not approved |
| `rocm-systems#10085` | partial + CI | PARTIAL approval + required gates genuinely red |
| `rocm-systems#10844` | re-run/rebase | stale `kBlockNameMap` build break (fixed on develop); diff untouched by it |
| `rocm-libraries#10233` | math CI | required Math CI genuinely failing; needs drill/rebase |

## The mistakes — two build breaks merged on "it's unrelated"

Both mistakes have the **same root cause**: a *build/compile* failure was bypassed on the author's or
requester's word that it was "unrelated / just script failures", without reading the build log. Both
produced the rule now at the top of the skill.

### 1. `rocm-systems#10179` — merged, broke the RDC build, reverted by Chiranjeevi

- **What happened.** `#10179` ("feat(amdsmi): expand `amdsmi_gpu_block_t` with new IP blocks") was
  bypass-merged citing the author's comment *"those are some script run failures. Failures are
  unrelated."* The failing check was in fact a real compile break: expanding the enum moved
  `AMDSMI_GPU_BLOCK_LAST` but did not update `projects/rdc`, which hard-coded the old tail, tripping a
  `static_assert` in `rdc_tests/test_common.cc:62` (`kBlockNameMap needs to be updated`).
- **Blast radius.** It landed on `develop` and broke the `dctools-core` (RDC) build for everyone,
  surfacing in Multi-Arch CI / ASAN at ~76% failure.
- **Recovery.** **Chiranjeevi Pattigidi reverted it (`#10947`)**; tracking issue `#10949` was filed;
  the author re-landed the expansion *with* the RDC fix in `#10973`.
- **Ripple.** For the rest of the rotation, any PR whose CI had run against the broken window inherited
  the same `kBlockNameMap` red — which is exactly why `#8690` and `#10844` were **refused** (their reds
  were the stale break, already fixed on develop) rather than merged. The mistake taught the fix.

### 2. A second override flagged by Rahul as a build failure

- A second bypassed PR was flagged by **Rahul** as causing / at risk of a build failure — the same
  pattern (a build-step red waved through as "unrelated"). The exact PR should be confirmed from the
  Teams thread before this row is finalized; it is recorded here because it is the corroborating second
  data point behind the Hard rule, not a one-off.
- **Lesson (identical to #1).** A red *build* step is never "unrelated" on anyone's say-so. Open the
  log, read the first error line. `error:` / `static assertion` / `undefined reference` / `ld:` /
  `CMake Error` at compile/link = **code**, blocks the merge, route to CODEOWNERS or revert. Only a
  failure that died *before* the compiler ran (fetch/network/toolchain/runner) is bypass-eligible on a
  build step.

## Skill changes this rotation produced

- **`process_merge_override_skill.md` — the Hard rule.** A failing build/compile step is never
  bypass-eligible unless the log proves it is infra; build-step failure ⇒ presumed code-caused; never
  take the requester's/author's "unrelated" word. `garden_bypass_single.ps1` enforces it in code — it
  refuses when a `-Fails` reason reads as a compile error unless `-AckBuildFailureIsInfra` is passed
  after the log is confirmed infra. (Direct product of incident #1.)
- **`check_approval.py` (new).** Resolves real approval from `latestOpinionatedReviews` + outstanding
  codeowner `reviewRequests` so a blank `reviewDecision` is no longer misread as "unapproved". Verdict
  `APPROVED` / `PARTIAL` / `NOT_APPROVED` / `CHANGES_REQUESTED`; only `APPROVED` clears the review axis.
- **`build_verdict_report.py` (new) + batch-first rule.** When the ask covers several PRs, triage all
  first and emit a verdict table (PR link + Teams permalink + can/cannot verdict), then ask which to
  merge before executing anything.
- **Single-vs-stacked detection hardened.** base==develop is necessary but **not** sufficient — a PR
  with children on its head is a stack (`--admin` refuses); check
  `gh pr list --base <this PR's head> --state open`.
- **Teams-thread-link requirement.** Every paste-ready `Merged!` / status / verdict reply must carry
  the `l/message` Teams permalink for that request. Baked into the skill's reply step, its traps list,
  and its description.
- **`teams_gardener_requests_skill.md` — widened merge-help classifier.** Match the merge verb in any
  inflection (`merge`/`merged`/`merges`/`merging`), the `Gardeners` plural, the "failures are
  unrelated / not related" override justification, and a bare "help + PR link" ask. Previously these
  real asks were silently dropped.

## Files

- `../../process_merge_override_skill.md` — the skill this rotation authored, Hard rule and all.
- `../../scripts/check_approval.py`, `garden_bypass_single.ps1`, `enqueue_bypass.py`,
  `garden_triage.ps1`, `build_verdict_report.py` — the override toolchain.
- `../../commands/pmo.md` — the `/pmo` command entry point.
