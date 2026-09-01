# pmo — Process a Merge-Override / Bypass request

> For use with **Cursor** custom commands (`/pmo`) or as a prompt for **Claude CLI**.

Context: Read [`gardener/process_merge_override_skill.md`](../process_merge_override_skill.md) first and follow it.

Use this when someone asks you to **override / force-merge / bypass** a PR that is `BLOCKED` because a
*required* gate is failing on what they believe are known infra flakes. This is the execution
counterpart to `/gr`: `/gr` classifies a blocked PR; `/pmo` takes the decision-to-override through to a
verified merge and a posted rationale.

## Instructions

1. I give you one PR (`/pmo <url>`) or several (a stack, a list, or "process the open override
   requests"). For a **batch**, do not merge anything yet — triage every PR (Steps 0–1) and emit the
   **verdict report table** (one row per open PR with the GitHub PR link, the Teams discussion
   permalink, and a can/cannot verdict), then ask which eligible PRs to merge.
2. **Step 0 — confirm it is actually a bypass case.** OPEN + not draft + BLOCKED by a *required* check.
   Resolve approval with `scripts/check_approval.py` (never trust a blank `reviewDecision`); only
   `APPROVED` clears the review axis — `PARTIAL` / `NOT_APPROVED` / `CHANGES_REQUESTED` route to
   CODEOWNERS. Enumerate the repo's required set with the `rulesets` API; everything else is advisory.
3. **Hard rule — read the build log yourself.** A failure inside the **build/compile** step is
   presumed code-caused and is **never** bypass-eligible unless the log proves it died before the
   compiler ran (fetch/network/toolchain/runner). Do **not** take the author's or requester's word that
   build failures are "unrelated" or "just script failures" — open the log and read the first error
   line. (This is why `rocm-systems#10179` reached `develop` and had to be reverted.)
4. **Step 1 — triage.** Prove every failing *required*-gate lane is infra/flake with the
   common-vs-distinctive method (`scripts/garden_triage.py --prs … --deep`). A lane that fails across
   unrelated PRs cannot be caused by any one diff; a lane that passes on the mainstream arch and only
   fails on a new/rare lane is a lane/arch issue, not the diff.
5. **Decide single vs stacked.** base==develop **and childless** ⇒ single ⇒ `garden_bypass_single.py`
   (`gh pr merge --admin`, gh token, no browser). Base is another PR's branch, **or** it has children
   on its head ⇒ stacked ⇒ `enqueue_bypass.py <PR> --go` (CDP `enqueue_stack`, authenticated Chrome on
   `:9222`), bottom → top.
6. **Execute.** Dry-run first, post the `#10579`-shape rationale comment, then merge and verify
   `state == MERGED`. Prefer a cheaper path when one exists — if the reds are already fixed on
   `develop`, a re-run / rebase clears them at zero commit cost and a bypass is neither needed nor
   allowed.
7. **Sweep + reply.** Sweep the merge SHA (`total_count == 0` push runs is a *finding*, not silence).
   Hand back the paste-ready `Merged! <comment-url>` line **with the Teams thread permalink** for that
   request — never a reply without its Teams thread link.

## Example usage

```
/pmo https://github.com/ROCm/rocm-systems/pull/10803
Reporter: "hip-tests failures are not related to this PR, can we get a merge override?"
```

Or a batch (report first, then ask which to merge):

```
/pmo process the open override requests
```
