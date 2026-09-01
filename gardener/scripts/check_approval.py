#!/usr/bin/env python3
r"""
check_approval.py <PR> [--repo owner/name] [--json]

Resolve the *real* code-review approval status of a PR, correctly handling the
case where GitHub's `reviewDecision` is null/empty.

Why this exists
---------------
`gh pr view --json reviewDecision` is NOT a reliable "is it approved?" signal.
GitHub returns `reviewDecision = null` (empty) in common situations even when
code owners HAVE approved -- e.g. when review requirements come from CODEOWNERS
and the PR touches paths owned by *several* teams: some owner teams approve while
others are still auto-requested. Treating a null/empty `reviewDecision` as
"not approved / no code-owner review" is wrong (it hides existing approvals) and
also fails to name the owner teams that are actually still outstanding.

What it does
------------
Pulls `reviewDecision`, `latestOpinionatedReviews` (each reviewer's final stance)
and `reviewRequests` (still-outstanding required reviewers, incl. CODEOWNERS
teams), then computes one verdict:

  APPROVED          reviewDecision == APPROVED, or (decision empty AND >=1
                    standing approval AND no outstanding codeowner requests AND
                    no changes-requested)
  CHANGES_REQUESTED a reviewer's latest stance is CHANGES_REQUESTED  -> hard stop
  PARTIAL           there ARE standing approvals but codeowner reviewers are
                    still outstanding -> code review is NOT complete; route the
                    remaining owners, do NOT bypass review
  NOT_APPROVED      reviewDecision == REVIEW_REQUIRED, or no standing approval
                    at all

Exit codes: 0 APPROVED, 2 PARTIAL, 3 NOT_APPROVED, 4 CHANGES_REQUESTED, 1 error.

IMPORTANT: a gardener bypass is for known-infra/flaky *CI*, never for unmet code
review. Only APPROVED is bypass-eligible on the review axis; PARTIAL / NOT_APPROVED
/ CHANGES_REQUESTED all route to CODEOWNERS.
"""
import argparse, json, subprocess, sys


def gql(repo_owner, repo_name, pr):
    q = """query($o:String!,$n:String!,$pr:Int!){
      repository(owner:$o,name:$n){pullRequest(number:$pr){
        reviewDecision
        reviewRequests(first:50){nodes{requestedReviewer{
          __typename ... on User{login} ... on Team{name slug}}}}
        latestOpinionatedReviews(first:50){nodes{author{login} state authorAssociation}}
      }}}"""
    p = subprocess.run(
        ["gh", "api", "graphql", "-f", "query=" + q,
         "-F", "o=" + repo_owner, "-F", "n=" + repo_name, "-F", "pr=%d" % pr],
        capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode("utf-8", "replace")[:800] or "gh api failed")
    return json.loads(p.stdout.decode("utf-8", "replace"))["data"]["repository"]["pullRequest"]


def classify(pr_data):
    decision = pr_data.get("reviewDecision")  # 'APPROVED'|'CHANGES_REQUESTED'|'REVIEW_REQUIRED'|None
    latest = pr_data.get("latestOpinionatedReviews", {}).get("nodes", [])
    approvals = [n["author"]["login"] for n in latest if n["state"] == "APPROVED"]
    changes = [n["author"]["login"] for n in latest if n["state"] == "CHANGES_REQUESTED"]

    pending = []
    for n in pr_data.get("reviewRequests", {}).get("nodes", []):
        rr = n.get("requestedReviewer") or {}
        if rr.get("__typename") == "Team":
            pending.append("team:" + (rr.get("slug") or rr.get("name") or "?"))
        elif rr.get("__typename") == "User":
            pending.append(rr.get("login") or "?")

    # changes requested always wins
    if changes or decision == "CHANGES_REQUESTED":
        verdict = "CHANGES_REQUESTED"
    elif decision == "APPROVED":
        verdict = "APPROVED"
    elif decision == "REVIEW_REQUIRED":
        verdict = "NOT_APPROVED"
    else:  # decision is None/'' -> disambiguate from the reviews + outstanding requests
        if approvals and not pending:
            verdict = "APPROVED"
        elif approvals and pending:
            verdict = "PARTIAL"
        else:
            verdict = "NOT_APPROVED"

    return {
        "reviewDecision": decision,
        "verdict": verdict,
        "approvals": approvals,
        "changesRequestedBy": changes,
        "outstandingReviewers": pending,
    }


EXIT = {"APPROVED": 0, "PARTIAL": 2, "NOT_APPROVED": 3, "CHANGES_REQUESTED": 4}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pr", type=int)
    ap.add_argument("--repo", default="ROCm/rocm-systems")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    owner, name = a.repo.split("/", 1)
    try:
        data = gql(owner, name, a.pr)
    except Exception as e:
        print("ERROR:", e, file=sys.stderr)
        return 1
    r = classify(data)
    if a.json:
        print(json.dumps(r, indent=1))
    else:
        print("PR #%d  reviewDecision=%r  -> %s" % (a.pr, r["reviewDecision"], r["verdict"]))
        if r["approvals"]:
            print("  approved by:", ", ".join(r["approvals"]))
        if r["changesRequestedBy"]:
            print("  CHANGES requested by:", ", ".join(r["changesRequestedBy"]))
        if r["outstandingReviewers"]:
            print("  still-requested codeowners:", ", ".join(r["outstandingReviewers"]))
        if r["verdict"] == "PARTIAL":
            print("  NOTE: partially approved -- outstanding code owners must still approve;")
            print("        this is NOT a review-bypass case. Route the remaining owners.")
    return EXIT[r["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
