# Gardener handover - Wk-36 (Mon 2026-08-24 -> Mon 2026-08-31) -> Wk-37

**Repos:** ROCm/rocm-systems, ROCm/rocm-libraries
**Gardener:** @amd-justchen
**Required sets (re-enumerated this rotation):** rocm-systems `develop` = `TheRock CI Summary` +
`HIP NVIDIA CI Summary`; rocm-libraries `develop` = `TheRock CI Summary` + `Math CI Summary` +
`pre-commit`. Everything else (Core, Code Coverage, rocprofiler-*, component CIs, docs, nightlies) is
**advisory** and never a bypass reason.

---

## Conclusion

Override desk processed **15 requests: 9 merged (all admin/CDP bypasses of known-infra failures), 6 left
open** - post-merge swept on all 9, **no code/compile regression traced to any bypass**; the only
merge decisions you inherit are the 6 open requests, and **none is blocked by code** - they need a
rebase/re-run on the now-fixed `develop`, a Math CI drill, or a code-owner, not an override.

## Do these first

| # | Action | PR | Why now |
| --- | --- | --- | --- |
| 1 | **Do nothing** on the 9 merged bypasses | see "Merged" | Post-merge swept clean of code regressions; the failures left are advisory or known infra. Re-running them is wasted work |
| 2 | **Re-check, don't override** - review flipped to APPROVED but still CI-BLOCKED | rocm-systems [#10085](https://github.com/ROCm/rocm-systems/pull/10085) | Was PARTIAL approval; now `reviewDecision=APPROVED`. Confirm with `check_approval.py`, then it's a CI question, not an approval one - required gates still failing, drill/rebase |
| 3 | **Rebase/re-run, do not bypass** - failures are the *stale* `kBlockNameMap` build break | rocm-systems [#10844](https://github.com/ROCm/rocm-systems/pull/10844), [#8690](https://github.com/ROCm/rocm-systems/pull/8690) | The break was fixed on develop ([#10947](https://github.com/ROCm/rocm-systems/pull/10947) revert + [#10973](https://github.com/ROCm/rocm-systems/pull/10973) reland). Neither diff touches rdc/amdsmi. Fresh CI on current develop clears them. [#8690](https://github.com/ROCm/rocm-systems/pull/8690) is also STACKED (child [#9632](https://github.com/ROCm/rocm-systems/pull/9632)) -> merge bottom-up. **Hard rule bars bypassing a compile failure.** |
| 4 | **Route to CODEOWNERS** | rocm-systems [#9431](https://github.com/ROCm/rocm-systems/pull/9431) | `REVIEW_REQUIRED`, zero failing checks - never a bypass |
| 5 | **Rebase onto fixed develop, do not bypass** | rocm-systems [#9738](https://github.com/ROCm/rocm-systems/pull/9738) | Real Linux `kBlockNameMap` compile break ([#10179](https://github.com/ROCm/rocm-systems/pull/10179) rerun) + not approved |
| 6 | **Drill/rebase, do not bypass** | rocm-libraries [#10233](https://github.com/ROCm/rocm-libraries/pull/10233) | Required `Math CI Summary` genuinely FAILURE + coverage-floor; 6-day stale run; not infra-proven |
| 7 | **Watch, no per-PR action** - subrepo mirror `patch does not apply` | [#10083](https://github.com/ROCm/rocm-systems/pull/10083), [#10653](https://github.com/ROCm/rocm-systems/pull/10653) (sys), [#10311](https://github.com/ROCm/rocm-libraries/pull/10311) (lib) | Repo-level mirror drift (`Generate and apply patches` / `Update Repositories in the Monorepo`). Not recoverable by re-run; owner is the mirror workflow, not the PR author |

## Open PRs (the inherited backlog - all re-pulled 2026-08-31, none auto-merge-armed)

| PR | What it is | State | Real blocker | Your move | Override? |
| --- | --- | --- | --- | --- | --- |
| [rocm-systems#10085](https://github.com/ROCm/rocm-systems/pull/10085) | Galantsev, stacked cuid tooling top | BLOCKED, review now APPROVED | required CI gates still failing | re-run on fresh develop; confirm approval via `check_approval.py` | No - CI, not approval |
| [rocm-systems#10844](https://github.com/ROCm/rocm-systems/pull/10844) | Papadopoulos | BLOCKED, APPROVED | TheRock CI failure = **stale** kBlockNameMap break (fixed on develop) | rebase/re-run on current develop | No (Hard rule) |
| [rocm-systems#8690](https://github.com/ROCm/rocm-systems/pull/8690) | Hui, **stacked** (child [#9632](https://github.com/ROCm/rocm-systems/pull/9632)) | BLOCKED, APPROVED | same stale kBlockNameMap break | rebase + re-run, then merge bottom->top | No (Hard rule) |
| [rocm-systems#9431](https://github.com/ROCm/rocm-systems/pull/9431) | Hosur | BLOCKED, REVIEW_REQUIRED | missing code-owner review | route to CODEOWNERS | No (approval) |
| [rocm-systems#9738](https://github.com/ROCm/rocm-systems/pull/9738) | SierraGuiza, [#10179](https://github.com/ROCm/rocm-systems/pull/10179) rerun | BLOCKED, not approved | **real** Linux kBlockNameMap compile break | rebase onto fixed develop + get review | No (build break) |
| [rocm-libraries#10233](https://github.com/ROCm/rocm-libraries/pull/10233) | Kim | BLOCKED, APPROVED | required Math CI Summary FAILURE + coverage floor | drill the Math CI failure / rebase | No (required gate) |

## Merged this week - the 9 override merges (post-merge swept 2026-08-31)

| PR | Merge commit | Post-merge verdict | Mirror |
| --- | --- | --- | --- |
| [rocm-systems#9031](https://github.com/ROCm/rocm-systems/pull/9031) | `388b5ee4` | TheRock CI push failure = known Windows gfx1151 build infra + `rocgdb-gpu (xfail)` + one flaky hip-tests shard. No code regression | ok |
| [rocm-systems#9584](https://github.com/ROCm/rocm-systems/pull/9584) | `bcc63b35` | clean (success + cancelled siblings) | ok |
| [rocm-systems#9696](https://github.com/ROCm/rocm-systems/pull/9696) | `848868dc` | failures are advisory `rocprofiler-sdk Code Coverage` + `Continuous Integration` only | ok |
| [rocm-systems#10083](https://github.com/ROCm/rocm-systems/pull/10083) | `911a8dc4` | required gates ok; **Merged PR to Patch Subrepos** `patch does not apply` | **mirror drift** |
| [rocm-systems#10084](https://github.com/ROCm/rocm-systems/pull/10084) | `f7fe8886` | failures = `RCCL coco nightly` + `RTD Docs Sync` (advisory/nightly) | ok |
| [rocm-systems#10653](https://github.com/ROCm/rocm-systems/pull/10653) | `77f6c619` | required gates ok; **Merged PR to Patch Subrepos** `patch does not apply` | **mirror drift** |
| [rocm-systems#10803](https://github.com/ROCm/rocm-systems/pull/10803) | `3571870e` | clean | ok |
| [rocm-systems#10953](https://github.com/ROCm/rocm-systems/pull/10953) | `3ffe951a` | failure = advisory `rocprofiler-systems-ci` only | ok |
| [rocm-libraries#10311](https://github.com/ROCm/rocm-libraries/pull/10311) | `070d115d` | merged on green (Math CI had just finished); failure = `Synchronize Subtrees` | **subtree drift** |

## Merge statistics - manual/override vs. not-overridden (per repo)

Produced by `gardener/scripts/merge_stats.py` (GraphQL `mergedBy`, window `2026-08-24..2026-09-01`).
"Manual/override" = merged **by the gardener account** (`gh pr merge --admin` or the CDP stacked
bypass); "not overridden" = auto-merge or a maintainer squash.

| Repo | Merged in window | Manual / override (by @amd-justchen) | Not overridden | Override share |
| --- | --- | --- | --- | --- |
| ROCm/rocm-systems | 271 | **45** | 226 | 16.6% |
| ROCm/rocm-libraries | 265 | **6** | 259 | 2.3% |
| **Total** | **536** | **51** | **485** | **9.5%** |

- rocm-systems manual set: [#5618](https://github.com/ROCm/rocm-systems/pull/5618), [#5638](https://github.com/ROCm/rocm-systems/pull/5638), [#9031](https://github.com/ROCm/rocm-systems/pull/9031), [#9584](https://github.com/ROCm/rocm-systems/pull/9584), [#9696](https://github.com/ROCm/rocm-systems/pull/9696), [#9776](https://github.com/ROCm/rocm-systems/pull/9776), [#10000](https://github.com/ROCm/rocm-systems/pull/10000), [#10011](https://github.com/ROCm/rocm-systems/pull/10011)-[#10015](https://github.com/ROCm/rocm-systems/pull/10015), [#10083](https://github.com/ROCm/rocm-systems/pull/10083),
  [#10084](https://github.com/ROCm/rocm-systems/pull/10084), [#10139](https://github.com/ROCm/rocm-systems/pull/10139), [#10157](https://github.com/ROCm/rocm-systems/pull/10157), [#10179](https://github.com/ROCm/rocm-systems/pull/10179), [#10210](https://github.com/ROCm/rocm-systems/pull/10210)-[#10213](https://github.com/ROCm/rocm-systems/pull/10213), [#10219](https://github.com/ROCm/rocm-systems/pull/10219), [#10310](https://github.com/ROCm/rocm-systems/pull/10310), [#10341](https://github.com/ROCm/rocm-systems/pull/10341), [#10359](https://github.com/ROCm/rocm-systems/pull/10359), [#10380](https://github.com/ROCm/rocm-systems/pull/10380), [#10396](https://github.com/ROCm/rocm-systems/pull/10396),
  [#10458](https://github.com/ROCm/rocm-systems/pull/10458), [#10487](https://github.com/ROCm/rocm-systems/pull/10487), [#10556](https://github.com/ROCm/rocm-systems/pull/10556), [#10563](https://github.com/ROCm/rocm-systems/pull/10563), [#10564](https://github.com/ROCm/rocm-systems/pull/10564), [#10579](https://github.com/ROCm/rocm-systems/pull/10579), [#10580](https://github.com/ROCm/rocm-systems/pull/10580), [#10606](https://github.com/ROCm/rocm-systems/pull/10606), [#10628](https://github.com/ROCm/rocm-systems/pull/10628), [#10653](https://github.com/ROCm/rocm-systems/pull/10653), [#10680](https://github.com/ROCm/rocm-systems/pull/10680), [#10682](https://github.com/ROCm/rocm-systems/pull/10682),
  [#10704](https://github.com/ROCm/rocm-systems/pull/10704), [#10802](https://github.com/ROCm/rocm-systems/pull/10802), [#10803](https://github.com/ROCm/rocm-systems/pull/10803), [#10845](https://github.com/ROCm/rocm-systems/pull/10845), [#10951](https://github.com/ROCm/rocm-systems/pull/10951), [#10953](https://github.com/ROCm/rocm-systems/pull/10953).
- rocm-libraries manual set: [#10749](https://github.com/ROCm/rocm-libraries/pull/10749), [#10825](https://github.com/ROCm/rocm-libraries/pull/10825), [#10957](https://github.com/ROCm/rocm-libraries/pull/10957), [#10979](https://github.com/ROCm/rocm-libraries/pull/10979), [#11211](https://github.com/ROCm/rocm-libraries/pull/11211), [#11249](https://github.com/ROCm/rocm-libraries/pull/11249).
- Note the count is every merge done from the gardener account (admin overrides **and** any
  gardener-driven squash, e.g. bump-PR sweeps), which is a superset of the 9 override *requests* in
  the table above. [#10179](https://github.com/ROCm/rocm-systems/pull/10179) appears here and is the reverted build-break mistake (see Lessons).
- Top non-gardener mergers (context): rocm-systems - marifamd x20, atgutier x20, kuhar x20;
  rocm-libraries - malcolmroberts x16, illsilin x10, KKyang x10.

## Unmerged-PR statistics

| Repo | Open PRs now (repo-wide) | Open **gardener requests** carried into Wk-37 |
| --- | --- | --- |
| ROCm/rocm-systems | 676 | 5 ([#10085](https://github.com/ROCm/rocm-systems/pull/10085), [#10844](https://github.com/ROCm/rocm-systems/pull/10844), [#8690](https://github.com/ROCm/rocm-systems/pull/8690), [#9431](https://github.com/ROCm/rocm-systems/pull/9431), [#9738](https://github.com/ROCm/rocm-systems/pull/9738)) |
| ROCm/rocm-libraries | 601 | 1 ([#10233](https://github.com/ROCm/rocm-libraries/pull/10233)) |
| **Total** | **1277** | **6** |

Of the 15 override requests this rotation: **9 merged, 6 refused/left open** (60% merge rate). All 6
open are documented above with their real blocker; none is override-eligible as it stands.

## Issues filed / referenced

| Issue/PR | What | Owner | Watch |
| --- | --- | --- | --- |
| [#10949](https://github.com/ROCm/rocm-systems/issues/10949) | kBlockNameMap build break tracker (from [#10179](https://github.com/ROCm/rocm-systems/pull/10179)) | TriveniTadapaneni | Closed by reland [#10973](https://github.com/ROCm/rocm-systems/pull/10973) |
| [#10947](https://github.com/ROCm/rocm-systems/pull/10947) | Revert of [#10179](https://github.com/ROCm/rocm-systems/pull/10179) | Chiranjeevi Pattigidi | Landed; unblocked develop |
| [#10973](https://github.com/ROCm/rocm-systems/pull/10973) | Reland gpu_block_t expansion **with** rdc fix | marifamd/bkanango | Landed |

## Daily infra - signatures seen this rotation

| Signature | Verdict | Re-run fix? |
| --- | --- | --- |
| `Fetch sources` timeout (~30 min) | Infra clone throttle | No - needs fresh dispatch |
| MI455 `gfx125X-dcgpu` build timeout / invalid-image | Infra (new lane) | No - fresh dispatch |
| `Driver / GPU sanity check`, `amd-smi static` exit 255 | Infra (runner) | Yes - usually |
| Windows `gfx1151` amd-mesa / `win_flex` third-party build | Infra (not the diff) | Sometimes |
| `Docker ... address pools fully subnetted` | Infra (subnet exhaustion) | Yes |
| **`kBlockNameMap` `static_assert` in rdc_tests/test_common.cc** | **CODE (build break)** - never bypass | No - rebase onto fixed develop ([#10973](https://github.com/ROCm/rocm-systems/pull/10973)) |
| `Merged PR to Patch Subrepos` / `Synchronize Subtrees` `patch does not apply` | Infra (mirror drift) | No - mirror workflow re-applies same git apply |
| rocprofiler-sdk Code Coverage / Continuous Integration, `rocprofiler-systems-ci` | Advisory | n/a - not required |

## Lessons

1. **A failing *build* step is never "unrelated" on the requester's/author's word.** [#10179](https://github.com/ROCm/rocm-systems/pull/10179) was merged on
   "those are script run failures, unrelated"; it was a real `kBlockNameMap` compile break, broke the
   RDC build on develop, was reverted ([#10947](https://github.com/ROCm/rocm-systems/pull/10947)) and relanded-with-fix ([#10973](https://github.com/ROCm/rocm-systems/pull/10973)). Open the build log,
   read the first error line. This produced the process-merge-override **Hard rule**.
2. **A stale build break masquerades as "your PR is broken."** [#8690](https://github.com/ROCm/rocm-systems/pull/8690)/[#10844](https://github.com/ROCm/rocm-systems/pull/10844) inherited the *fixed*
   kBlockNameMap failure from a broken base - rebase/re-run, don't bypass, don't route to owners.
3. **`reviewDecision` lies - use `check_approval.py`.** [#10085](https://github.com/ROCm/rocm-systems/pull/10085) read PARTIAL then APPROVED as owner
   teams cleared; a blank/empty value is not "unapproved".
4. **`head_sha` run queries need the FULL 40-char SHA.** A truncated SHA returns `total_count=0`,
   which looks like a dropped-push finding but is a query bug. Confirm with the commit check-runs API.
5. **Single vs stacked picks the merge tool.** `--admin` for base==develop-and-childless; CDP
   `enqueue_stack` bottom->top for stacks ([#10083](https://github.com/ROCm/rocm-systems/pull/10083)/[#10084](https://github.com/ROCm/rocm-systems/pull/10084) this week). Each no-ops on the other shape.

## Details / appendix

- Full override verdict ledger with per-PR reasons and merge SHAs is in the session `ovr` table and
  the process-merge-override rationale comments posted in each PR thread (public, authoritative).
- Merge-stats raw dump: `merge_stats.json` (per-repo counts + manual PR lists).
- My working notes are in a private scratch dir and are deliberately not linked here; nothing in them
  is needed to act on this handover.
