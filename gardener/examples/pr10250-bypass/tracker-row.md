# Tracker row format

One row per PR, edited in place as the case evolves. Never a prose section, never the reply text —
that lives in the `-respond.md` file.

| Day | PR | Issue | Triage keypoint | Override | Post-merge / status |
| --- | --- | --- | --- | --- | --- |
| 0810 | [#10250](https://github.com/ROCm/rocm-libraries/pull/10250) `[hipblaslt]` Equality tuning (gfx1250) | [TheRock#7170](https://github.com/ROCm/TheRock/issues/7170) clone throttling · [#10522](https://github.com/ROCm/rocm-libraries/pull/10522) rocjitsu OpenMP path · [TheRock#7161](https://github.com/ROCm/TheRock/issues/7161) sles16 | **Infra, and a re-run cannot fix it** — both runs complete, `BLOCKED` + `APPROVED`, `pre-commit` and `Math CI Summary` green, so only `TheRock CI Summary` blocks. Its 3 reds: `rocjitsu race check` (gfx94X + gfx950) fixed on `develop` Aug 9, after this run's Aug 7 merge base; `Build (gfx125X-dcgpu)` hit the 30-min `amd-llvm` clone timeout a 3rd time while sibling `Build (gfx950-dcgpu)` went green in the same run. **The gap:** `gfx125X-dcgpu` *is* gfx1250, so no lane built the tuned arch; blast radius bounded because codegen filters logic files by `ARCHES` | **Done** — `3a08f1b4`, `JIRA ID` preserved. A label toggle would have cleared `rocjitsu` but gfx125X is 3/3 on #7170, so waiting bought no gfx1250 evidence and missed the cut-off | Rationale posted as [comment 5247165841](https://github.com/ROCm/rocm-libraries/pull/10250#issuecomment-5247165841), merged `--admin --squash`. Next: `develop` post-merge + Patch Subrepos mirror |

Columns, and why each exists:

| Column | Purpose |
| --- | --- |
| Day (`MMDD`) | Ordering, and it shows how long a case has been open |
| PR | Number, link, short title — enough to recognise without opening it |
| Issue | Every known issue you linked, so the next gardener inherits the baseline |
| Triage keypoint | **Infra** / **Not infra** in bold, then the mechanism. If a conclusion was overturned, say so in the same cell in one clause rather than keeping the old analysis |
| Override | `Done` / `Ignore` / `Not needed` / `n/a`, plus the reason the cheaper path was or was not taken |
| Post-merge / status | What was sent, what merged, and what still needs watching |

Keep two more sections at the bottom of the tracker:

- **Not signed off on** — the boundary you stated publicly on each case. This is what protects you
  when a numerics or perf issue surfaces later.
- **Open items** — one row each, struck through with the answer when closed rather than deleted.
