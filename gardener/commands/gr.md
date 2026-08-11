# gr — Monorepo Gardener Request

> For use with **Cursor** custom commands (`/gr`) or as a prompt for **Claude CLI**.

Context: Read `gardener/monorepo_gardener_skill.md` first and follow it.

Use this when a request arrives in the **Gardening - rocm-libraries** or **Gardening - rocm-systems**
channel, or when someone tags the gardener on a PR.

## Instructions

1. I give you a PR URL (and possibly run/job URLs, plus the reporter's message). Work out the repo
   from the URL — `rocm-libraries` and `rocm-systems` have **different required check sets**, so
   enumerate them with the `rulesets` API instead of assuming.
2. **Classify the ask before triaging**: confirmation-only, bypass/merge request, or "looks stuck".
   Do not answer a request for confirmation with an offer to bypass.
3. **Check whether the runs have finished.** If they have not, look only at the required set. If
   nothing there has failed yet, say so and stop — do not classify in-flight advisory reds, and do not
   give me a conditional "if it goes green then X, otherwise Y" answer that waiting resolves.
4. Classify every red into infra/flaky, code-related, no-result (zero signal), or advisory. Prefer the
   two hard proofs (unreachable diff, same-run sibling control) over "it passed on a re-run".
5. Produce three files under `triage/week<WW>/`:
   - `MMDD-pr<PR>-respond.md` — the reply, in the fixed three-part shape (conclusion + decision
     sentence, `| Red check | Keypoint |` table, at most one coverage-gap sentence), with everything
     longer under `# Optional detail` and an `## If someone pushes back` section. Newest reply first.
   - `MMDD-pr<PR>-<topic>.md` — the triage note: why, with evidence and timestamps.
   - `tracker.md` — one table row per PR. Edit the existing row when a case evolves; do not append a
     second row and do not keep superseded analysis.
6. Never put reply text in the tracker, and never restate the same fact in two files.
7. If a bypass is on the table, walk the preconditions explicitly, then answer "would waiting fix
   this?", then re-pull live state immediately before executing. Post the rationale in the thread
   before merging, and preserve the author's squash body so `JIRA ID` / `ISSUE ID` lines survive.
8. Keep it short. The reply must be sendable as-is; your chat answer to me is at most 10 sentences —
   the conclusion, the decision, the files you touched. No evidence walkthrough unless I ask.

## Example usage

```
/gr https://github.com/ROCm/rocm-libraries/pull/10250
Reporter: "3 checks are failing, all look like infra. Can you merge today? BKC cut-off."
```

Or with explicit job links:

```
/gr https://github.com/ROCm/rocm-systems/pull/1234
failed: https://github.com/ROCm/rocm-systems/actions/runs/<RUN>/job/<JOB>
```
