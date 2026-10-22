# Monorepo gardener — reference

Detail for [SKILL.md](SKILL.md). Section numbers are the ones that file cites. Read the section you were sent to.

## Contents

- [5. The two hard proofs that a red is unrelated to the diff](#5-the-two-hard-proofs-that-a-red-is-unrelated-to-the-diff)
- [6. Re-run, re-dispatch, or push — the merge-base rule](#6-re-run-re-dispatch-or-push--the-merge-base-rule)
- [7. When `Math CI Summary` is red (rocm-libraries)](#7-when-math-ci-summary-is-red-rocm-libraries)
- [8. Approval-blocked, not CI-blocked](#8-approval-blocked-not-ci-blocked)
- [9. Bypass: decide, then execute](#9-bypass-decide-then-execute)
- [10. When one fault blocks the whole queue, escalating *is* the work](#10-when-one-fault-blocks-the-whole-queue-escalating-is-the-work)
- [12. Trap list](#12-trap-list)

## 5. The two hard proofs that a red is unrelated to the diff

Both beat *"it passed on a re-run"*, because neither depends on luck.

**a) The change is unreachable.** Read the diff for a guard, a path filter, or an architecture the
change does not touch. One PR's entire change sat inside `if(HIPBLASLT_ENABLE_DEVICE AND NOT WIN32)`,
so a Windows build failure could not structurally be caused by it. Same for workflow files: find which
workflow consumes the changed YAML, and reds from every other workflow are excluded by construction.

**Expand the architecture family before claiming unreachable.** CI lanes are named by **family**
(`gfx125X-dcgpu`), diffs by **architecture** (`.../Logic/asm_full/gfx1250/...`). They are often the
same thing, and confusing them turns *the only lane that could have validated the change* into
*an unrelated lane*.

```bash
rg -n "gfx125X" TheRock/build_tools/github_actions/*amdgpu_family_matrix.py
rg -n "gfx1250" TheRock/cmake/therock_amdgpu_targets.cmake
# therock_add_amdgpu_target(gfx1250 ... FAMILY dcgpu-all ...)  ⇒ gfx125X-dcgpu *is* gfx1250
```

While in that matrix file, grep for `# No <arch> hardware available for testing yet` — if present,
even a green lane is build-only and the reply must say so.

**b) A control that differs only in the change.** Strongest form is a **sibling job in the same run,
same commit, same diff**: one green, one stuck at exactly 30 minutes in `Fetch sources`, and the
verdict is locked with no cross-branch archaeology.

```bash
gh api "repos/$REPO/actions/runs/<RUN_ID>/jobs?per_page=100" --paginate \
  --jq '.jobs[] | select(.name|test("Build \\(")) | "\(.conclusion)\t\(.started_at)\t\(.name)"'
```

Next best is branch history — a force-push is a free controlled experiment. Code changed, failure list
unchanged ⇒ not the code.

```bash
gh api "repos/$REPO/actions/runs?event=pull_request&per_page=100&branch=<HEAD_BRANCH>" \
  --jq '.workflow_runs[] | select(.name=="TheRock CI")
        | "\(.id) \(.head_sha[0:7]) \(.created_at) \(.conclusion // "running")"'
```

**c) A third proof of equal strength: several unrelated PRs reporting byte-for-byte identical
numbers.** A coverage ratchet failing at `73.39% → 70.83% (-2.56)` on three different PRs, on a file
in none of their diffs, is a `develop`-level gate fault. Confirm the baseline is the stale side:

```bash
gh pr diff $PR --repo $REPO --name-only            # regressed file absent from the diff
git log --format='%h %ad %s' --date=short <gate_commit>..origin/develop -- <regressed_source_file>
git log --format='%h %ad %s' --date=short <gate_commit>..origin/develop -- <baseline_json>
```

Source file has new commits, baseline file has none ⇒ stale baseline. This class can be neither
re-run nor bypassed: it needs a fix-forward on `develop` plus a rebase. Route to the author of the
commit that moved the source file first, the gate author second, and **never** ask the blocked author
to refresh the baseline inside their own PR — that makes them vouch for someone else's coverage drop.

**Two inverted-control traps.** `develop` being green proves nothing when the job is path-filtered:
it shows as `skipped`, and `skipped` is not a pass. And docs-only branches never dispatch heavy lanes
at all, so they cannot serve as a control either. Always confirm the control job actually ran:

```bash
gh api "repos/$REPO/actions/runs/<RUN>/jobs?per_page=100" --jq '.jobs[] | "\(.conclusion) | \(.name)"'
```

**Stacked PRs produce vacuous green.** With the base still pointing at the parent branch, the diff is
empty or tiny, every `Build` is `skipped`, and the summary passes for free. Once the base is
repointed at `develop`, the diff becomes the whole stack and that earlier green covered nothing. Read
the merge base before believing any green (§6).

---

## 6. Re-run, re-dispatch, or push — the merge-base rule

Pre-submit CI builds `refs/pull/<N>/merge`, the merge of the PR with its base. **A re-run replays that
same merge commit.** It clears a flake; it can never pick up a fix that landed on `develop`
afterwards. Getting this wrong wastes hours and is the most common mistake in this role.

Read the merge base of any past run straight out of the Setup job log:

```bash
sid=$(gh api "repos/$REPO/actions/runs/<RUN>/jobs?per_page=50" \
  --jq '.jobs[]|select(.name=="Setup")|.id' | head -1)
gh api repos/$REPO/actions/jobs/$sid/logs | rg -o "HEAD is now at .* Merge .* into .*"
# HEAD is now at 314aa79 Merge 4d5c723 into 223bff09   ← 223bff09 is the merge base

gh api repos/$REPO/compare/<fix_sha>...<merge_base> --jq '{status,ahead_by,behind_by}'
# behind_by=0 and status=ahead ⇒ the merge base already contains that fix
```

| Method | Cost | Notes |
| --- | --- | --- |
| `gh run rerun --failed <RUN_ID>` | Cheapest | Failed jobs plus dependents only. **Not allowed while the run is in progress** — wait for it to finish |
| Toggle a label | Zero commits, branch untouched | Re-dispatches GitHub Actions with a fresh merge base. Does **not** trigger internal gates |
| Merge `develop` into the branch (push) | One command | Re-triggers Actions *and* internal gates. Required when `Math CI Summary` is also red |
| Rebase onto `develop` | Cleanest, needs the author | |

Label toggle, because it is the underused one. `therock-ci.yml` listens to `labeled`/`unlabeled`
without filtering on which label, so removing and re-adding **a label the PR already has** leaves the
final label set byte-identical. Do not invent a new label, and first confirm the label is not one the
matrix parses (in rocm-libraries only `test:*` and `test_type:*` are read by
`.github/scripts/therock_configure_ci.py`; `ci`, `project: *` and friends are safe).

```bash
# gh pr edit --add-label fails with "Projects (classic) is being deprecated" — use REST
gh api -X DELETE repos/$REPO/issues/$PR/labels/<label>
gh api -X POST   repos/$REPO/issues/$PR/labels -f 'labels[]=<label>'
gh api repos/$REPO/labels --paginate --jq '.[].name'   # gh label list truncates
```

Both events dispatch a run and `concurrency: cancel-in-progress` cancels the first, so read the rollup
by newest `startedAt`. Before pushing anything, confirm approval survives — on rocm-libraries
`develop` both flags are `false`, so it is free:

```bash
gh api repos/$REPO/rulesets/<ID> \
  --jq '[.rules[]|select(.type=="pull_request")|.parameters
         |{dismiss_stale_reviews_on_push,require_last_push_approval}]'
```

**A required check that never dispatched cannot be re-run at all** — there is no run object, and
`workflow_dispatch` usually is not wired up. Diff the required set against what actually exists on the
head SHA:

```bash
SHA=$(gh pr view $PR --repo $REPO --json headRefOid --jq .headRefOid)
gh api "repos/$REPO/commits/$SHA/check-runs?per_page=100" \
  --jq '.check_runs[] | "\(.name) | \(.status)/\(.conclusion)"'
gh api "repos/$REPO/commits/$SHA/status" --jq '.state, (.statuses[] | "\(.context) | \(.state)")'
```

Missing entirely means the event was dropped — several workflows vanishing at once is lost delivery,
not a config bug. Auto-merge does not save you here: the check will never report, so it never fires,
and *waiting is a dead end*. Before burning a multi-hour CI cycle to recover one lint check, **run the
missing check by hand** and say so in the thread. Copy the workflow's own command; the author's
self-report is not evidence, your own run is:

```bash
git fetch origin pull/$PR/head:pr$PR && git checkout pr$PR
pre-commit run --from-ref origin/develop --to-ref HEAD   # extra_args from pre-commit.yml
```

---

## 7. When `Math CI Summary` is red (rocm-libraries)

rocm-libraries has two independent CI systems. **Do not write "the internal CI is not visible to
me"** — the internal Math CI Jenkins answers a plain `curl` from an AMD workstation with no auth, and
a required gate being red means you drill until you reach the assertion.

```bash
MATHCI="https://<internal-math-ci-host>"     # ask in the gardening channel / SRE playbook
G="$MATHCI/job/rocm-libraries/job/status-gate/job/<component>/job/PR-$PR/lastBuild"
curl -s -o /dev/null -w "%{http_code}\n" --max-time 20 "$G/wfapi/describe"
```

`status-gate` is only an aggregator; the real failure is in the `precheckin` build it points at. Four
hops, all `wfapi`, all JSON:

```bash
curl -s "$G/wfapi/describe"                                   # which stage is red
curl -s "$G/execution/node/<STAGE_ID>/wfapi/describe"         # NOT PASSING child nodes
curl -s "$G/execution/node/<NODE_ID>/wfapi/log"               # log contains the precheckin build URL
P="$MATHCI/job/rocm-libraries/job/precheckin/job/<component>/job/PR-$PR/<build>"
curl -s "$P/wfapi/describe"                                   # per-arch Compile / Package / Test
```

Job path is `job/rocm-libraries/job/<pipeline>/job/<component>/job/PR-<n>/<build>`, with `<pipeline>`
one of `status-gate`, `precheckin`, `preliminary`, `static-analysis`, `codecov`,
`tensilelite-unit-codecov`.

`wfapi/log` returns only the last ~10 KB, so the gtest tallies and the failing assertion are usually
truncated. For the full log pull `consoleText` (tens of MB, contains NUL bytes, so `rg -a`):

```bash
curl -s "$P/consoleText" -o console.txt
rg -a -n "^\[==========\] [0-9]+ tests?|^\[  PASSED  \]|^\[  FAILED  \] [0-9]+ tests?," console.txt
```

Reading a gtest failure:

- **Compare architectures inside the same build.** The same test passing on two architectures and
  failing on a third points at the machine. A host-side change that is genuinely broken fails on all
  of them.
- **Scroll up ~20 lines for a resource error.** `Insufficient device memory to allocate (16 GB) as the
  available device memory is (11 GB)` followed by `hipErrorInvalidValue` and then `invalid argument`
  is one cascade. Criterion: HIP error codes mean infra; tolerance or mismatch messages mean numerics.
- **Report the denominator.** "39,706 passed / 3 failed" is far more persuasive than "3 failures".

Finally, `Math CI Summary  pass  ...  SKIPPED BY MATH-CI` is **not** a green light — the state is pass
but not one job ran. Using Math CI as the authoritative signal during a GitHub outage only holds when
it actually ran and reported *"All math-ci jobs passed"*. Otherwise call out the coverage gap.

---

## 8. Approval-blocked, not CI-blocked

`BLOCKED` with **zero failing checks** is a process problem. Do not open a log.

```bash
gh pr view $PR --repo $REPO \
  --json mergeStateStatus,reviewDecision,latestReviews,reviewRequests,files
```

| Symptom | Conclusion |
| --- | --- |
| No failing check + `REVIEW_REQUIRED` | Approval blocked, not infra |
| Already has an approval, still `REVIEW_REQUIRED` | The CODEOWNERS team does not match |
| `reviewRequests` contains a `Team` entry | That team is the missing gate; individual requests are cosmetic |

Match CODEOWNERS **by changed file path**, not by what the change is about:

```bash
gh api "repos/$REPO/contents/.github/CODEOWNERS?ref=develop" --jq '.content' \
  | base64 -d | rg -n "<path fragment>"
gh api orgs/ROCm/teams/<team-slug>/members --paginate --jq '.[].login'   # read:org is enough
```

Known rocm-libraries trap: the whole `/.github/` directory belongs to one reviewers team, so a PR
touching only `.github/workflows/*` cannot be unblocked by the component's own team lead, however
relevant that lead is to the change. Use `orgs/.../teams/<slug>/members` and grep it yourself; the
`memberships/<user>` endpoint is the one that demands `admin:org`.

**Do not @-mention the whole team.** Name one or two people, and say why:

```bash
# who actually touched this file (strongest, and cheapest)
gh api "repos/$REPO/commits?path=<file>&per_page=15" \
  --jq '.[] | "\(.commit.author.date[0:10])\t\(.author.login)"'
# who approved this file before
gh api repos/$REPO/pulls/<n>/reviews --jq '[.[]|select(.state=="APPROVED")|.user.login]'
# who is still active (reviews in the last 90 days)
gh api "search/issues?q=repo:$REPO+is:pr+reviewed-by:<user>+updated:>=<date>&per_page=1" --jq .total_count
# Teams needs a real name, a GitHub login will not resolve
gh api users/<login> --jq '{name,company}'
```

Priority: **blame author who is in the team** > team member who approved this file before > anyone
else in the team. When reconstructing precedent from old PRs, verify the PR really touched the target
path (`--json files`) — an `in:path` search returns PRs that only edited a component-level CODEOWNERS,
whose approvers prove nothing. Naming the wrong person in a public channel is worse than naming nobody.

**Never bypass this.** None of the four bypass preconditions hold, and pushing it through means
skipping a gate that is working correctly and vouching for files you do not own. Bypass exists for
broken infra, not for slow humans.

**Delivery boundary: route it and close it.** Chasing an approval is not gardener work. Your two
deliverables are *identify the real blocker* and *route it to someone who can unblock it*. If that
person is out of office, hand the thread onward — cc their manager, or ask in the channel for another
team member — rather than adding it to your own tracker. A gardener who adopts every stuck PR gets
buried in non-CI work and the real infra signal gets diluted. Re-engage only if it becomes a CI issue.

---

## 9. Bypass: decide, then execute

Every precondition in the repo's `gardening.md` must hold: run finished, failing check is **required**,
known issue filed and linkable, unrelated to the diff, reproduces elsewhere or survives a re-run, and
nothing new hiding behind it.

Then ask what that list does not: **would waiting fix this?**

| Situation | Answer |
| --- | --- |
| Lane broken for weeks, issue open, no assignee | Will not repair itself → bypass |
| Platform outage, one unlucky runner | Clears on its own → wait, then re-run |
| Root cause already fixed on `develop`, this run predates it | Fresh dispatch, not a re-run (§6) |
| Author has auto-merge on and the check *will* report | Nothing for you to do |
| Required check never dispatched | Waiting is a dead end (§6) |

**"Not yet" needs a dated condition** attached, or it reads as stalling: *"if only `<issue>` remains and
no code owner has replied by `<date>`, I will push it through."*

**A bypass offered to you is still your call.** A reporter saying *"the change is small, I'd be OK with
a bypass"* removes their objection, not the requirement to keep the tree green. Refuse when there is a
cheaper path — a red **required** check is not a broken gate to route around; half those reds may
already be fixed on `develop`, and a label toggle buys a fresh merge base at zero commit cost. Fixing
the signal always beats bypassing it.

**Your rationale has a shelf life.** One draft argued *"a fresh run would die in checkout the same
way"*, and by the time it was executed hours later the new run had cleared checkout and 20 test shards
were queued — including a lane that had never run before. Re-pull live state immediately before
executing, and re-verify specifically the predictions about the future, since those expire first. Also
confirm which run the red actually came from: one PR's red `TheRock CI Summary` belonged to a
**cancelled** run while the live run had not reported yet.

**Before claiming "zero test evidence", measure the blast radius.** A lane that never ran is riskier to
skip than one that is red for a known reason, but that is the start of the analysis, not the end. The
real question is *does the change's radius have authoritative coverage independent of this fault?*

```bash
# 1. is the change component-exclusive? (do not assume same-named dirs are shared)
rg -l "<changed module>" projects/<other_component>          # zero hits ⇒ its reds cannot be related
# 2. are the builds green? build and test pools are often different runners
gh api "repos/$REPO/actions/runs/<RUN>/jobs?per_page=100" \
  --jq '.jobs[]|select(.name|test("Build"))|"\(.conclusion) \(.name)"'
# 3. does the internal gate cover the affected component?
gh pr checks $PR --repo $REPO | rg -i "mci/.*precheckin"
# 4. how is the artifact filtered? (arch-filtered codegen bounds the damage)
rg -n "LOGIC_FILTER|ARCHES" projects/<comp>/cmake/*.cmake projects/<comp>/*/CMakeLists.txt
```

"Zero build evidence for this arch" **plus** "the blast radius is one lane that is already blocked" is
an acceptable risk. Without the second half it is a blind push.

### Execution

```bash
# reuse the author's squash body or the JIRA ID / ISSUE ID lines are lost
gh pr view $PR --repo $REPO --json autoMergeRequest --jq '.autoMergeRequest.commitBody' > /tmp/body.md
gh pr merge $PR --repo $REPO --squash --admin \
  --subject "<original title> (#$PR)" --body-file /tmp/body.md
```

Post the rationale to the thread **before** merging, and state explicitly what you are not vouching
for — numerics, performance, any lane that never ran.

When the reply goes into a GitHub comment rather than Teams, two things bite: a bare `#NNNN` resolves
to the *current* repo, so always write `ROCm/TheRock#7161` in full; and run and job URLs must be
spelled out, since a markdown link with an empty target renders as nothing. Read the posted body back
and fix it before moving on:

```bash
gh api repos/$REPO/issues/comments/<id> --jq .body
```

### After merging

Pushing it through makes the outcome yours.

```bash
# 1. post-submit runs on the merge commit. A develop push normally does dispatch a full set —
#    measured 2026-08-10, 6 of 8 merge commits carried TheRock CI + Component CI + pre-commit +
#    clang-tidy + Merged PR to Patch Subrepos. So total_count=0 is a FINDING, not the default:
#    it means the push event itself was dropped, and an on:push workflow cannot be replayed.
gh api "repos/$REPO/actions/runs?head_sha=<merge_sha>&per_page=100" --paginate \
  --jq '.workflow_runs[] | select(.event != "issue_comment") | "\(.event) \(.name) \(.conclusion)"'

# 2. did the subrepo mirror actually happen? "success" is not proof
gh api repos/$REPO/actions/jobs/<JID>/logs \
  | rg -i "Processing subtree|Cloned |Pushed changes|patch does not apply"
gh api "repos/ROCm/<subrepo>/commits?sha=develop&per_page=5" \
  --jq '.[]|"\(.sha[0:9]) \(.commit.committer.date) \(.commit.message|split("\n")[0])"'
```

**Check whether the component mirrors at all before chasing step 2** — most do not, and the ones that
do not will never produce a mirror run no matter how long you wait:

```bash
gh api repos/$REPO/contents/.github/repos-config.json --jq '.content' | base64 -d \
  | jq -r '.repositories[] | "\(.category)/\(.name)\t\(.url)\tpush=\(.auto_subtree_push)"'
# measured 2026-08-10: auto_subtree_push=false for projects/miopen, projects/hipdnn,
# shared/origami, shared/stinkytofu and all four dnn-providers/*
```

Mirror caveats worth knowing: the apply step is guarded by a subtree-detection step, so a green run may
have done nothing; `sha=develop` is required because the standalone repo's *default* branch may be
years stale; `patch does not apply` means the subrepo has drifted and re-running the manual workflow
will fail identically, since it calls the same `git apply`. Also notify any downstream PR you unblocked
that it can rebase.

For the batch version of all of this — sweeping post-merge CI across every PR you merged in a week,
and turning the result into the handoff artifacts — see
[`gardener-rotation-handover`](../gardener-rotation-handover/SKILL.md).

---

## 10. When one fault blocks the whole queue, escalating *is* the work

Bypassing per PR costs a bypass every time and fixes nothing. The deliverable is a number, a specific
fixable thing, and one owner.

1. **Attribute to the first failing step, not to the job.** Failed job lists are full of aggregators
   (`Output failed jobs`, `Evaluate workflow results`, `<X> CI Summary`, Teams notifiers), which counts
   one root cause four or five times and makes the number less credible, not more. One real day: 116
   failed jobs → 79 derived → 37 leaf failures, 62% sharing a single step.
2. **Measure the failing step's duration.** All values identical means a hard timeout you can point at
   a specific `timeout-minutes`; scattered values mean genuine network jitter. 22 of 22 landing in
   30.0–30.1 minutes is what turned "the network is bad" into an actionable ticket.
3. **Take the union of several snapshots.** `runs/<id>/jobs` shows the latest attempt only, so any
   re-run hides earlier victims. Two scans 2.5 hours apart read as 14 PRs then 11 PRs — looking like
   relief, while the union was 17. Either union your snapshots or write *"as of `<time>`, understated
   because of re-runs"*.
4. **Diff against a workflow in the same repo that is not failing**, argument by argument. One case
   came down to the failing workflow omitting `--depth 1` and not enabling the repo's own git mirror
   mechanism, which the healthy workflow used.

Hand the fleet to the SRE rotation rather than triaging it yourself when jobs are queued or stuck
across many PRs, runners are offline, or an architecture label has no capacity. Note that "no test
results" has at least two distinct fleet causes and they need different owners: dying in transfer
(clone throttled) versus never getting a machine (capacity). The tell for the latter is a job with a
`started_at`, no step ever executing, and `conclusion=cancelled`.

---

## 12. Trap list

1. A killed job is **zero signal**, not failure evidence — and not evidence of success either.
2. A re-run replays the same merge SHA; it cannot pick up a `develop` fix.
3. `runs/<id>/jobs` returns the latest attempt only; `--paginate` when `total_count > per_page`.
4. `statusCheckRollup` returns superseded check runs; group by name, take the newest `startedAt`.
5. `StatusContext` entries keep their verdict in `.state`; `.conclusion` is `null`.
6. `cancelled` is not `failure`; `skipped` is not a pass.
7. `SKIPPED BY MATH-CI` is not a green light.
8. `codecov/patch` measures this diff and is a real reviewer signal; `codecov/project/*` is a standing
   repo threshold. Do not bundle them.
9. A description-policy bot red (missing `JIRA ID` / `ISSUE ID`) is not CI, and only the author can fix it.
10. Lanes are named by architecture **family**, diffs by **architecture**. Expand before calling a diff
    unreachable.
11. A stacked PR's green summary is vacuous until its base is `develop`.
12. `gh pr edit --add-label` fails on the Projects-classic deprecation; use the REST label endpoints.
    `gh label list` truncates; `gh api repos/<r>/labels --paginate` does not.
13. `gh run rerun` is rejected while the run is in progress.
14. `gh run view --job <id> --log` can come back empty; prefer `gh api .../actions/jobs/<id>/logs`.
    That endpoint also refuses while the parent run is in progress.
15. An in-flight fix PR touching the same file does not prove causation. Disprove it by finding a
    branch **without** the fix that passes the same lane.
16. Check whether a re-run is already in flight before reaching for a bypass. On one PR, waiting
    produced 21/21 green tests the bypass would have skipped.
17. The requester is often not the author. Read the whole thread — a reviewer asking *"do we have any
    test results?"* is a different question from *"are these failures related?"*, and answering only
    the second leaves them unanswered.
18. **Zero workflow runs on a merge commit is a finding, not silence.** It means the push event was
    dropped, and an `on: push` workflow cannot be replayed — so that commit gets no post-submit CI and
    no subrepo mirror, ever.
19. **The failing *step* is the verdict, not the failing job.** `Set up job`, `Fetch sources`,
    `Driver / GPU sanity check` and `Run setup test environment workflow` are all zero signal without
    opening a log. A job with `conclusion: failure` and no failed step was cancelled by a sibling.
20. **Once the author arms auto-merge, stop.** A green run merges it with their own body and `JIRA ID`
    intact. Starting a re-run can trip `cancel-in-progress` and kill queued shards along with it.

---

