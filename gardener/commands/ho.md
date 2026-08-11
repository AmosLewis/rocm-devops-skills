# ho — End-of-rotation handover

> For use with **Cursor** custom commands (`/ho`) or as a prompt for **Claude CLI**.

Context: Read `gardener/handover_skill.md` first and follow it.

Use this on the **last day of your gardener week**, before the Tuesday handoff.

## Instructions

1. I give you the week number and my tracker (or just the list of PRs I handled). Work out the repos
   involved — required check sets differ per repo, so re-enumerate them with the `rulesets` API.
2. **Re-pull live state for every PR before writing anything.** Authors rebase and arm auto-merge
   overnight; a tracker written yesterday is already stale. Flag every PR whose `headRefOid` moved or
   whose `autoMergeRequest` is now non-null, and change the recommended action to "do nothing".
3. **Run the post-merge sweep on every merge commit**: workflow runs with `--paginate`, then the
   failing **step** for each red run. Only open a log when the failing step is
   `Build therock-artifacts and therock-dist` or `Test`. Report `total_count == 0` as a finding.
4. For each post-merge red, tell me which of these it is: known infra, develop-wide breakage the PR
   merged on top of (prove it by timestamp), cancelled sibling, or **actually attributable to the
   PR**. Only the last one needs action from me.
5. Check `auto_subtree_push` in `.github/repos-config.json` **before** opening any mirror item, then
   verify surviving ones at the destination with `sha=develop`.
6. Produce two files:
   - `MMDD-handover-week<N+1>.md` — the detailed doc in the fixed section order (conclusion, do these
     first, open PRs, merged this week, issues filed, daily infra, lessons, details). The infra table
     must have a "does a re-run fix it?" column.
   - `MMDD-handover-week<N+1>-teams.md` — the Teams message: phrases not sentences, bold verb first
     on every bullet, no markdown tables.
7. **Run the reachability check** on both files. Any path pointing at my private notes is a dead link
   for the reader — replace it with a public URL (this repo plus section number, a PR comment
   permalink, an issue link, or the upstream `docs/gardening.md`).
8. List every promise I made publicly this week (bypass offers, dated fallbacks) with its condition
   and deadline, so it transfers with the rotation.
9. Keep the Teams message under ~350 words. Your chat answer to me is at most 10 sentences: what
   changed since the tracker, anything actually attributable to a PR I merged, and the files written.

## Example usage

```
/ho week32, ROCm/rocm-libraries
PRs: 10245 10180 10016 10372 7228 9785 10499 9615 9642 9293 10250 10588 10507
Tracker: @triage/week32/tracker.md
```
