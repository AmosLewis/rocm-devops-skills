# Example: bypass request on ROCm/rocm-libraries#10250 (Aug 10, 2026)

A real end-to-end case for [`monorepo_gardener_skill.md`](../../monorepo_gardener_skill.md). The ask
was *"3 checks are failing, all look like infra — can you merge today, we are at the BKC cut-off"*.

Outcome: merged with `--admin --squash` after posting the rationale in the thread.

What it demonstrates:

| Point in the skill | How it shows up here |
| --- | --- |
| Enumerate the required set first (§1) | Only `TheRock CI Summary` mattered; sles16, `Multi-Arch CI Summary` and `codecov/project/*` collapse into one advisory row |
| A re-run cannot pick up a `develop` fix (§6) | `rocjitsu race check` was fixed on `develop` a day *after* this run's merge base was cut, so attempt 2 replayed the broken state |
| Same-run sibling control (§5b) | `Build (gfx950-dcgpu)` went green on attempt 2 while `Build (gfx125X-dcgpu)` timed out again — same run, same commit, same diff |
| Expand the architecture family (§5a) | `gfx125X-dcgpu` **is** gfx1250, so the "unreachable diff" argument did *not* apply and the coverage gap had to be stated |
| Bound the blast radius before accepting a gap (§9) | The codegen filters logic files by `ARCHES`, so a defect could only surface in the one lane already blocked |
| The fixed three-part reply shape (§11) | `pr10250-respond.md` — conclusion, red table, one gap sentence; everything else under `# Optional detail` |

Files:

- `pr10250-respond.md` — the reply as sent, plus the detail kept in reserve
- `tracker-row.md` — the single tracker row this case produced
