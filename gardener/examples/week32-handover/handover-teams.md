# Teams handover message — real example (rocm-libraries, Wk-32, Aug 4–10 2026)

Reviewer names replaced with role placeholders. 341 words. Posted with the detailed handover doc
attached.

---

**Gardener handover: Wk-32 (Aug 4–10) → Wk-33** — details in the attached doc.

**Week:** 15 requests · 8 merged (4 admin overrides) · 7 open · post-merge checked on all 8, **zero regressions** · nothing open blocked by code, only infra or missing review.

**Actions**

- **#10507 — merge, `--admin --squash`.** Only real decision. sles16 fix, `APPROVED`. Reds = 6 × #7170 + 1 × #6857, `queued` 11h, no re-run clears. Bypass promised EOD Aug 11, condition met. Body: `ISSUE ID: https://github.com/ROCm/TheRock/issues/7161` → then close #7161.
- **#9615, #9293 — no action.** Fresh heads + auto-merge armed. Self-merge on green; intervening cancels their runs.
- **#9642 — ask author:** job-level re-run of `Windows gfx1151 / Test miopen (shard 3 of 4)` + add `JIRA ID`. No override, real abort.
- **#10588 — get a reviewer:** route via `@ROCm/hipblaslt-reviewers`. No override, confirmed compile defect.
- **#10347 — chase review:** build-infra owners. Math CI red is in-flight, don't triage yet.

**Daily infra — none fixed by re-running**

- **TheRock-Infra#602** — jobs `queued` for hours, no GPU runner. Worst one right now.
- **TheRock#7170** — `Fetch sources` clone timeout. @\<assignee\>
- **TheRock#6857** — Windows `hipInfo.exe` sanity timeout. Zero signal.
- **TheRock#6207** — ASAN 100% red on develop, not in required set, blocks nothing.
- **#10522 · #9160→#10531** — stale-merge-base traps. Need a fresh base.

**Watch:** TheRock#7170 · #7161 · #7167 · #10591 · #10611 · #10462

**Two gotchas**

- Required set is **per repo** — `gh api repos/<repo>/rulesets` before calling anything "the blocker". Cost me two public retractions.
- 3 merged PRs never mirrored to their standalone subrepo: #10016 + #10180 (Aug 6 outage ate the push event, unrecoverable), #7228 (`git apply` failed). `Merged PR to Patch Subrepos` failing ~33%. May need manual cherry-picks.

Ping me on anything.
