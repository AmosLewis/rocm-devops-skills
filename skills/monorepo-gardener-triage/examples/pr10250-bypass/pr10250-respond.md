**Created:** 2026-08-10 10:55 (UTC-7)
**Last updated:** 2026-08-10 16:28 (UTC-7)
**Outcome:** rationale posted, then merged `3a08f1b4` with `--admin --squash`, `JIRA ID` line preserved

PR: [#10250](https://github.com/ROCm/rocm-libraries/pull/10250) `[hipblaslt] Equality tuning for BF16, MXF8, MXF4, F8 MAF`
Ask: override / merge today — BKC release code cut-off
Classification: **Infra** — all 3 reds inside the required check are known, and a re-run cannot clear them

| Reply | Short version | Sent |
| --- | --- | --- |
| 1 | Both runs finished; 3 reds all known infra → `--admin` squash, gfx1250 build gap stated | **Sent** 16:26 UTC-7 as [comment 5247165841](https://github.com/ROCm/rocm-libraries/pull/10250#issuecomment-5247165841); merged `3a08f1b4` |

# Short reply — this is what gets sent

## Reply 1 short

> Both attempt-2 re-runs are done — `TheRock CI`
> [31159672227](https://github.com/ROCm/rocm-libraries/actions/runs/31159672227) and
> `TheRock Multi-Arch CI`
> [31159672377](https://github.com/ROCm/rocm-libraries/actions/runs/31159672377).
> `Math CI Summary` + `pre-commit` green, approved, no unresolved threads, and all 3 reds in
> the required `TheRock CI Summary` are known infra — so I will `--admin` squash for the BKC cut-off
> with the `JIRA ID` line preserved.
>
> | Red check | Keypoint |
> | --- | --- |
> | `rocjitsu race check` (gfx94X **and** gfx950) | `OpenMP runtime not found …/libomp.so`; fixed on `develop` by ROCm/rocm-libraries#10522 (Aug 9). Your run was created Aug 7, so no re-run can pick it up |
> | `Build (gfx125X-dcgpu)` | 30-min `Fetch sources` timeout cloning `amd-llvm` (ROCm/TheRock#7170), 3rd time. Sibling `Build (gfx950-dcgpu)` went green in the same run on the same commit ⇒ clone throttling, not your YAML |
> | sles16, `Multi-Arch CI Summary`, `codecov/project/*` | Outside the required set |
>
> One gap I would rather state than paper over: `gfx125X-dcgpu` **is** gfx1250, so no lane ever built
> the arch you are tuning — that evidence is your tensilelite / hipblaslt-bench run. Since the logic
> files are arch-filtered, the only lane that can regress on `develop` is the one #7170 already blocks.

# Optional detail — reference only, quote if pushed

## Reply 1 detail

Required set on `develop` (ruleset 5167088): `TheRock CI Summary` ❌, `Math CI Summary` ✅,
`pre-commit` ✅. `mergeable: MERGEABLE`, `reviewDecision: APPROVED` (Aug 6), 0 unresolved review
threads. Both runs completed: TheRock CI 34 success / 4 failure / 3 skipped, Multi-Arch CI
47 success / 2 failure / 26 skipped.

| Red check | Keypoint |
| --- | --- |
| `rocjitsu race check (gfx94X-dcgpu)` and `(gfx950-dcgpu)` | Exit ~50 s in on `OpenMP runtime not found: …/build/lib/llvm/lib/x86_64-unknown-linux-gnu/libomp.so`. Fixed on `develop` by [#10522](https://github.com/ROCm/rocm-libraries/pull/10522) (Aug 9 17:59 UTC, touches only `.github/scripts/run_rocjitsu_hipblaslt_race_check.sh`). Run 31159672227 was created Aug 7 07:56 UTC, so attempt 2 replayed a pre-fix merge SHA — a re-run cannot fix this, only a new merge base can |
| `Build (gfx125X-dcgpu)` | `Cloning into '…/compiler/amd-llvm'` 18:02:33 → killed 18:32:31 = the 30-min step timeout → [TheRock#7170](https://github.com/ROCm/TheRock/issues/7170). Third consecutive occurrence on this branch. **Control in the same run:** `Build (gfx950-dcgpu)` failed the same way on attempt 1 and came back `success` on attempt 2 at 17:58 — same commit, same diff, so this is the clone throttling |
| `TheRock CI Summary` | Pure aggregate of the three above |
| `Test RPM Install - sles16`, `Multi-Arch CI Summary`, `Test ROCm wheels py3.12 ubuntu24.04` (cancelled) | Inside `TheRock Multi-Arch CI`, whose summary is **not** in the required set. sles16 is [TheRock#7161](https://github.com/ROCm/TheRock/issues/7161) |
| `codecov/project/hipBLASLt` | Standing repo threshold, not required; `codecov/patch` is green |

Green that carries weight: the internal `precheckin(hipblaslt)` gate passed Aug 7 on these exact four
files (and the same gate caught something in the stacked follow-up #10588's `Compile stage`, so it is
not a rubber stamp); gfx94X, gfx950 and Windows gfx1151 builds all green; the full gfx94X test set
green (6 shards hipblaslt, 6 rocblas, 6 hipsparselt, plus hipblas and tensilelite).

Blast radius: hipBLASLt's device-library codegen takes `ARCHES` and filters logic files, so
`gfx1250_*_UserArgs.yaml` is not read by a gfx942/gfx950/gfx1151 build. A defect in this diff can only
surface in the gfx125X-dcgpu lane — the one #7170 is already blocking.

Not signing off on: gfx1250 numerics or performance, and gfx1250 build correctness. The matrix has no
gfx1250 test hardware (`# No gfx1250 hardware available for testing yet` in the family matrix file), so
even a green gfx125X lane would have been build-only.

## If someone pushes back

- "Just re-run it" → attempts 1 and 2 both failed `rocjitsu` on the same `libomp.so` line; the fix is
  on `develop` and a re-run replays the Aug 7 merge SHA.
- "gfx125X failed, so your change is broken" → the sibling gfx950 build went green in the same run on
  the same commit after failing identically on attempt 1; the failing step is `Fetch sources`, before
  any hipBLASLt code is configured.
- "Why not toggle a label for a fresh merge base" → it would clear `rocjitsu`, but gfx125X has now hit
  #7170 three times out of three, so it would not reliably produce the gfx1250 build evidence either,
  and it restarts a multi-hour chain past the cut-off.
