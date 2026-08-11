# Skill: End-of-rotation handover — post-merge sweep, handover doc, Teams message

> Run this on the **last day of your gardener week**, before the Tuesday handoff. Companion to
> [`monorepo_gardener_skill.md`](monorepo_gardener_skill.md) (per-request triage) and
> [`bumppr_skill.md`](bumppr_skill.md) (bump PR sweep). The normative policy for the role is each
> repo's own `docs/gardening.md` and wins over anything here.

All commands verified against `ROCm/rocm-libraries` on **2026-08-10**. Rulesets and workflow names
change — re-enumerate rather than trusting the tables below.

---

## If you read nothing else

1. **Sweep post-merge CI on every PR you merged.** You own the outcome of a bypass until the merge
   commit is green or explained. §1
2. **Read the failing *step*, not the failing job.** The step name is the verdict; only two step names
   ever require opening a log. §1.3
3. **Zero workflow runs on a merge commit is a finding, not a query bug.** §1.4
4. **Check `auto_subtree_push` before opening a "confirm the mirror" item** — most components do not
   mirror at all. §1.5
5. **Re-pull every open PR's head and auto-merge state before you write anything.** Authors fix their
   own PRs overnight and will invalidate your TODO list. §2.1
6. **Your successor cannot read your notes.** Every link in the handover must be a public URL. §3
7. **Teams message = phrases, what to do. Attachment = sentences, why and how.** §4

---

## 0. The 60-second version

```bash
REPO=ROCm/rocm-libraries
PRS="10245 10180 10016 10372 7228 9785 10499 9615 9642 9293 10250 10588 10507"

# 1. current state of everything you touched (note mergeCommit + autoMergeRequest)
for p in $PRS; do
  gh pr view $p --repo $REPO --json number,state,isDraft,mergedAt,mergeCommit,\
mergeStateStatus,reviewDecision,headRefOid,autoMergeRequest
done

# 2. post-merge runs on each merge commit  (--paginate is mandatory, see §1.2)
gh api "repos/$REPO/actions/runs?head_sha=$SHA&per_page=100" --paginate \
  --jq '.workflow_runs[] | select(.event != "issue_comment")
        | "\(.event)\t\(.name)\t\(.status)/\(.conclusion)\t\(.id)"' | sort -u

# 3. for every red run, the failing STEP (this is where the verdict comes from)
gh api "repos/$REPO/actions/runs/$RID/jobs?per_page=100" --paginate \
  --jq '.jobs[] | select(.conclusion=="failure")
        | "\(.id)\t\(.name)\tSTEP=\([.steps[]?|select(.conclusion=="failure")|.name]|join(","))"'
```

---

## 1. The post-merge sweep

### 1.1 Why it is not optional

Merging with `--admin` makes the outcome yours. The sweep is also where the evidence you *knowingly
skipped* finally shows up: on `rocm-libraries` #10250 the pre-merge `gfx125X-dcgpu` build timed out
three times, so the arch the PR tuned was never built — and the post-merge run on the merge commit
built it successfully in 24 minutes, retroactively closing the one open risk in that bypass.

Do it as a batch at end of week, not per PR. Three commands cover a whole rotation.

### 1.2 `--paginate`, always

A commit can carry 60+ `Docs Preview` runs from `issue_comment` events. Without `--paginate` they
fill page 1 and the run you want is silently absent — which reads as "no run was dispatched" and is
wrong. Filter `issue_comment` out, and check `.total_count` against `per_page` before believing a
zero.

### 1.3 The step name is the verdict

The job name tells you which lane died. The **step** name tells you which phase, and the phase is the
classification. Most reds need no log read at all:

| Failing step | Verdict | Read the log? |
| --- | --- | --- |
| `Set up job` | Runner or action-download failure. Zero signal (typical during a GitHub incident) | No |
| `Fetch sources` | Clone timeout / throttling. Zero signal | No |
| `Driver / GPU sanity check` | Died before any test ran. Zero signal | No |
| `Run setup test environment workflow` | Environment provisioning. Zero signal | No |
| `Run rocjitsu race check` | Known runtime-path issue — check whether the run predates the fix | No |
| **`Build therock-artifacts and therock-dist`** | **Possibly real.** Open it | **Yes** |
| **`Test`** | **Possibly real.** Open it | **Yes** |
| No failed step, but `conclusion: failure` | The job was **cancelled** by a sibling failure. Zero signal | No — check `.steps[].conclusion` for `cancelled` |

Only when you land in the bold rows:

```bash
gh api repos/$REPO/actions/jobs/$JID/logs \
  | rg -n -iE "error:|FAILED:|ninja: build stopped|CMake Error|fatal error"
```

Across a 15-PR week this reduced to **two** logs actually worth opening, and one of those turned out
to be a repo-wide breakage rather than the PR's fault (§1.4).

### 1.4 Two failure modes that look like the PR but are not

**A develop-wide breakage the PR merged on top of.** A post-merge build red can come from a bad
commit already on `develop` at the moment your PR merged. Test it by timestamp, not by reading code:

```bash
# when did the merge land, and when was the breaking change reverted?
gh pr view <PR>      --repo $REPO --json mergedAt --jq .mergedAt
gh pr view <REVERT>  --repo $REPO --json mergedAt --jq .mergedAt
# merge inside [breakage, revert] ⇒ the commit carries the bad state ⇒ not the author's fault
```

Real case: a merge at 16:23 UTC failed on a config type error introduced earlier that day and
reverted at 19:44 UTC — 3h21m *after* the merge. Nothing to do with the PR.

**Zero runs at all.** An empty result from §0 step 2 is a **finding**, and a serious one:

```bash
gh api "repos/$REPO/actions/runs?head_sha=$SHA&per_page=100" --paginate --jq '.total_count'
# 0  ⇒ the push event itself was dropped (platform incident)
```

Post-submit and subrepo-mirror workflows trigger `on: push`. A dropped push event **cannot be
replayed**, so those merge commits get no post-merge CI and no mirror, permanently. Two merge commits
in one week hit this during a GitHub Actions incident. Say so explicitly in the handover — the next
gardener cannot discover it by looking at the PR.

> If a skill or runbook tells you `total_count=0` is normal for this repo, verify before believing
> it. Measured on 2026-08-10: **6 of 8** merge commits carried a full push run set
> (`TheRock CI`, `Component CI`, `pre-commit`, `clang-tidy`, `Merged PR to Patch Subrepos`).

### 1.5 Do not open a mirror item without checking the flag first

Most components do **not** mirror to a standalone repo. Read the config before adding a TODO:

```bash
gh api repos/$REPO/contents/.github/repos-config.json --jq '.content' | base64 -d \
  | jq -r '.repositories[] | "\(.category)/\(.name)\t\(.url)\tpush=\(.auto_subtree_push)"'
```

Measured 2026-08-10 on `rocm-libraries`: `auto_subtree_push=false` for `projects/miopen`,
`projects/hipdnn`, `shared/origami`, `shared/stinkytofu` and **all four `dnn-providers/*`**. Two of
that week's merges touched only those paths, so chasing their mirrors would have been wasted work.

For components that *do* mirror, a green mirror run is not proof — verify at the destination, and
pass `sha=develop` because the standalone repo's default branch may be years stale. Full method in
[`monorepo_gardener_skill.md` §9](monorepo_gardener_skill.md).

Three distinct mirror outcomes, with different owners:

| Signature | Meaning | Recoverable? |
| --- | --- | --- |
| No `push` run on the merge commit | Push event dropped during an incident | **No** — `on: push` cannot be replayed. Needs a manual cherry-pick |
| `patch does not apply` | The standalone repo has drifted | Not by re-running — the manual workflow calls the same `git apply` |
| Destination has the commit | Mirrored | — |

---

## 2. The handover document

### 2.1 Refresh live state first, or you will hand over stale instructions

On the last night of one rotation, two authors independently rebased and armed auto-merge. Both had
been sitting in the tracker as "pending an override decision" — that instruction was now wrong, and
acting on it would have cancelled their in-flight runs.

```bash
gh pr view <PR> --repo $REPO --json headRefOid,autoMergeRequest,mergeStateStatus,reviewDecision
```

**`autoMergeRequest != null` means hands off.** A green run merges the PR with the author's own body,
`JIRA ID` intact. Intervening is actively harmful: starting a re-run once triggered
`cancel-in-progress` and killed 20 already-queued test shards.

### 2.2 Fixed structure

| Section | Content | Rule |
| --- | --- | --- |
| **Conclusion** | One sentence | Must answer "what do I do Monday morning". Example: *"15 requests, 8 merged, 7 open — nothing open is blocked by code, and the only merge decision you inherit is #10507."* |
| **Do these first** | `# / Action / PR / Why now` table | Priority order. **Must include the "do nothing" items** |
| **Open PRs** | `PR / What it is / State / Real blocker / Your move / Override?` | One row per PR. "Real blocker" is usually not the loudest red |
| **Merged this week** | `PR / Merge commit / Post-merge verdict / Mirror` | The §1 output |
| **Issues filed** | `Issue / What / Owner / What to watch` | Include unfiled drafts and who must approve them |
| **Daily infra** | `ID / Signature / Verdict / Does a re-run fix it?` | **Highest reuse value of the whole document** |
| **Lessons** | ~5 imperatives | Only ones that cost you time this week |
| **Details** | Appendix | Everything a reader may skip |

Two rules that carry most of the value:

- **The infra table needs a "does a re-run fix it?" column.** "Just re-run it" is the most common and
  most expensive wrong advice in this role. Stale merge bases and clone throttling both survive a
  re-run; only a fresh dispatch or a new base clears them.
- **"Do nothing" must be an explicit numbered action with its consequence spelled out.** A
  conscientious successor will otherwise touch an auto-merge-armed PR and break it.

### 2.3 State every promise you made in public

If you told a reporter *"if only known infra reds remain by EOD Thursday I'll honour your bypass
offer"*, that commitment transfers with the rotation. An unrecorded promise becomes a broken one.
Give the successor the deadline, the condition, and the exact command including the
`ISSUE ID:` / `JIRA ID:` line for the squash body.

### 2.4 Re-enumerate the required set for **every** repo you covered

```bash
for r in rocm-libraries rocm-systems; do
  echo "== $r"; gh api repos/ROCm/$r/rulesets --jq '.[] | "\(.id) \(.name) \(.target)"'
done
gh api repos/ROCm/<repo>/rulesets/<ID> \
  --jq '[.rules[] | select(.type=="required_status_checks")
         | .parameters.required_status_checks[].context]'
```

No admin rights needed. The sets genuinely differ per repo while the two `docs/gardening.md` files
differ by only ~6 lines, which makes them very easy to conflate — the exact trap a single-gardener
rotation creates. Naming a non-required check as "the blocker" is the most common way to have to
retract in public.

---

## 3. Reachability check — your successor cannot read your notes

Most gardeners keep working notes in a private repo. Every reference to one is a dead link for the
reader. Run this before you send:

```bash
rg -n "\.\./|~/|_skill\.md|notes/|triage/week|solution/|internal wiki" handover*.md
# every survivor must be a public URL, or delete it
```

What to link instead, in order of usefulness:

| Instead of | Link |
| --- | --- |
| Your method notes | This repo, **with the section number** (`monorepo_gardener_skill.md` §6), not just the repo root |
| Your per-PR reply drafts | **The comment permalink in the PR thread.** Already public, and more authoritative than a draft |
| Your weekly tracker | The PR and issue links in your own tables — they *are* the evidence anchors |
| An internal SOP or wiki page | The upstream `docs/gardening.md`, or the PR that is updating it |

This only works if you posted every verdict in the thread as you went. That is the practical payoff
of the "rationale goes in the thread, not just in your notes" rule — it is what makes a handover
linkable at all.

Close with one explicit line so nobody thinks they are missing required material:

> My working notes are in a private repo and are deliberately not linked here; nothing in them is
> needed to act on this handover.

---

## 4. The Teams message: phrases, not sentences

**Division of labour: the message says what to do, the attachment says why and how.** Any explanatory
clause belongs in the attachment.

One real message went 700+ words → 541 → **341** over two passes. Both passes did the same thing:
turned sentences into phrases.

| | Too long | Right |
| --- | --- | --- |
| Action item | `#10507 — merge it.` followed by five sentences | `**#10507 — merge, --admin --squash.**` followed by phrases |
| Evidence | *"whose reds are 6 × #7170 and 1 × #6857, and the run has been queued for 11 hours"* | `Reds = 6 × #7170 + 1 × #6857, queued 11h, no re-run clears` |
| Infra list | One sentence each | `**TheRock#7170** — Fetch sources clone timeout. @<assignee>` |
| Stats | A paragraph | `15 requests · 8 merged (4 admin overrides) · 7 open` |

Rules:

1. **The first bold word of every bullet is the verb** — `merge`, `no action`, `ask author`,
   `get a reviewer`, `chase review`. Scanning the bold text alone must be enough.
2. One bullet per PR. Do not merge two PRs into one bullet.
3. Stats line uses `·` separators, never prose.
4. **"No action" gets its own bullet plus its consequence** (`Self-merge on green; intervening
   cancels their runs`).
5. **No markdown tables** — Teams renders them poorly. Tables belong in the attachment.

Skeleton:

```text
**Gardener handover: Wk-<N> (<dates>) → Wk-<N+1>** — details in the attached doc.

**Week:** <N> requests · <N> merged (<N> admin overrides) · <N> open · post-merge checked on all
<N>, **zero regressions** · nothing open blocked by code, only infra or missing review.

**Actions**
- **#<PR> — <verb>.** <phrase>. <phrase>. <phrase>.
- ...

**Daily infra — none fixed by re-running**
- **<issue>** — <signature>. <owner>
- ...

**Watch:** <issue> · <issue> · <issue>

**Two gotchas**
- <phrase>
- <phrase>

Ping me on anything.
```

---

## 5. Re-check your own published claims

A sweep produces measured data, which is exactly what invalidates assertions written from memory.
Before you finish:

```bash
rg -n "total_count|is normal|never|always|no heavy CI" gardener/*.md
```

Take every absolute (`never`, `always`, `is normal`) that this week's data touched and re-verify it.
A published runbook line saying *"`total_count=0` is normal"* would have caused the next gardener to
skip past the single most important finding of the week (§1.4). A stale runbook is worse than no
runbook, which is also why every gate claim in this repo ships with the command that verifies it.

---

## 6. Checklist

- [ ] Live state re-pulled for every open PR (`headRefOid`, `autoMergeRequest`, `mergeStateStatus`)
- [ ] Post-merge runs checked on every merge commit, `--paginate` used
- [ ] Every red classified by **failing step**; logs opened only for `Build …` / `Test`
- [ ] `total_count == 0` cases called out as findings, not silence
- [ ] `auto_subtree_push` checked before any mirror item; mirrors verified at the destination
- [ ] Required set re-enumerated per repo via `rulesets`
- [ ] Every public promise (bypass offers, deadlines) written down with its condition
- [ ] Handover doc contains a "do nothing" action where auto-merge is armed
- [ ] Infra table has the "does a re-run fix it?" column
- [ ] Reachability check run; no private paths survive
- [ ] Teams message is phrases, no tables, bold verb first
- [ ] Absolutes in your published skills re-verified against this week's data
