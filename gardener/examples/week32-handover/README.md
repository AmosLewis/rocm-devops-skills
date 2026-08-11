# Example: end-of-rotation handover (rocm-libraries, Wk-32, Aug 4–10 2026)

A real handover after a 15-request week: 8 merged (4 with an admin override), 7 open. Included
because the post-merge sweep produced three findings that no amount of per-PR triage would have
surfaced.

## What this example demonstrates

| Section of [`handover_skill.md`](../../handover_skill.md) | How it shows up here |
| --- | --- |
| §1.1 the sweep closes your own open risks | #10250 was merged without a `gfx1250` build (the lane timed out 3×). The post-merge run built it successfully in 24 min, retroactively supplying the missing evidence |
| §1.3 the step name is the verdict | 15 failing jobs across the week reduced to **two** logs worth opening. Everything else was `Set up job`, `Fetch sources`, `Driver / GPU sanity check` or a cancelled sibling |
| §1.4 develop-wide breakage | #9785's post-merge build red came from a bad commit reverted **3h21m after** the merge — proven by timestamp, not by reading code |
| §1.4 `total_count == 0` is a finding | #10016 and #10180 have **zero** push runs. The incident dropped the push event, so no post-submit CI and no mirror will ever run for them |
| §1.5 check the flag before chasing a mirror | Two of the week's merges touched only `auto_subtree_push=false` paths — the mirror TODO was never real |
| §2.1 refresh live state | Two PRs sitting in the tracker as "pending an override decision" had been rebased with auto-merge armed overnight. The recommended action flipped to "do nothing" |
| §2.3 promises transfer | A bypass offered publicly with an EOD deadline became the successor's first action item |
| §4 phrases, not sentences | [`handover-teams.md`](handover-teams.md) — 700+ words → 541 → 341 across two passes |

## The three findings

1. **Two merge commits will never be mirrored.** A dropped push event cannot be replayed, so the
   standalone subrepos are permanently missing those changes. Only a manual cherry-pick recovers
   them. A third failed on `git apply` because the standalone repo had drifted.
2. **Queue starvation had overtaken clone throttling** as the worst infra fault — jobs cleared
   checkout and then sat 4–11 hours without ever getting a GPU runner. Same visible symptom as a
   clone timeout, different owner, different fix. This is why "just re-run it" failed as advice all
   week.
3. **A published runbook line was wrong.** It claimed `total_count=0` was normal for post-submit runs
   in this repo; measurement showed 6 of 8 merge commits carried a full push run set. Following it
   would have hidden finding 1. See §5.

## Files

- [`handover-teams.md`](handover-teams.md) — the channel message as sent, with reviewer names
  replaced by role placeholders.

The detailed companion document is not published here (it links to a private notes repo in places),
but its section order is specified in [`handover_skill.md` §2.2](../../handover_skill.md) and the
reachability rule that catches exactly that problem is in §3.
