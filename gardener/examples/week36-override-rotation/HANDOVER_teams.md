**Gardener handover: Wk-36 (Aug 24 -> Aug 31) -> Wk-37** - details in the attached doc.

**Week:** 15 override requests | 9 merged (all admin/CDP bypasses of known-infra failures) | 6 open | post-merge swept on all 9, **zero code regressions** | nothing open blocked by code, only stale-build / missing-review / Math-CI.

**Merge stats (whole repo, Aug 24-Sep 1):** rocm-systems 271 merged | 45 manual/override by gardener (16.6%) | 226 not overridden. rocm-libraries 265 merged | 6 manual (2.3%) | 259 not overridden. Open backlog now: rocm-systems 676 | rocm-libraries 601.

**Actions**
- **[#10085](https://github.com/ROCm/rocm-systems/pull/10085) (sys) - re-run, don't override.** Review flipped PARTIAL->APPROVED. Now a CI question, not approval. Confirm with check_approval.py.
- **[#10844](https://github.com/ROCm/rocm-systems/pull/10844) (sys) - rebase/re-run, don't override.** Failure = stale kBlockNameMap build break, fixed on develop ([#10947](https://github.com/ROCm/rocm-systems/pull/10947) + [#10973](https://github.com/ROCm/rocm-systems/pull/10973)). Diff untouched by it.
- **[#8690](https://github.com/ROCm/rocm-systems/pull/8690) (sys) - rebase/re-run, don't override.** Same stale build break. Also STACKED (child [#9632](https://github.com/ROCm/rocm-systems/pull/9632)), merge bottom->top.
- **[#9431](https://github.com/ROCm/rocm-systems/pull/9431) (sys) - route to CODEOWNERS.** REVIEW_REQUIRED, no failing checks. Never a bypass.
- **[#9738](https://github.com/ROCm/rocm-systems/pull/9738) (sys) - route 2 code owners, then re-run.** PARTIAL approval (outstanding: xiaogang-chen-amd, dayatsin-amd) - not a bypass. Build failure is the stale [#10179](https://github.com/ROCm/rocm-systems/pull/10179) kBlockNameMap break in rdc (fixed on develop [#10973](https://github.com/ROCm/rocm-systems/pull/10973)), not this kfdtest-only diff.
- **[#10233](https://github.com/ROCm/rocm-libraries/pull/10233) (lib) - drill Math CI / rebase.** Required Math CI Summary FAILURE + coverage floor. Not infra-proven.
- **No action** on the 9 merged bypasses. Self-swept clean; remaining failures advisory or known infra. Re-running is wasted work.

**Watch - subrepo mirror drift, not a per-PR fix**
- **Merged PR to Patch Subrepos** `patch does not apply` on [#10083](https://github.com/ROCm/rocm-systems/pull/10083), [#10653](https://github.com/ROCm/rocm-systems/pull/10653) (sys) | **Synchronize Subtrees** on [#10311](https://github.com/ROCm/rocm-libraries/pull/10311) (lib). Owner = mirror workflow, not the author.

**Daily infra - none fixed by re-running**
- **kBlockNameMap static_assert** - real build break; rebase onto develop [#10973](https://github.com/ROCm/rocm-systems/pull/10973), never bypass.
- **Fetch sources / MI455 gfx125X timeout** - clone/lane infra; needs fresh dispatch, not re-run.
- **Windows gfx1151 amd-mesa / win_flex** - third-party build infra, not the diff.

**Two gotchas**
- A failing BUILD step is never "unrelated" on the author's word - open the log (this is the [#10179](https://github.com/ROCm/rocm-systems/pull/10179) lesson -> the Hard rule).
- head_sha run queries need the FULL 40-char SHA; a truncated one returns total_count=0 and looks like a dropped push.

Ping me on anything.
