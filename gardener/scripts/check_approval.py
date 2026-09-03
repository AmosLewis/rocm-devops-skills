#!/usr/bin/env python3
r"""
check_approval.py <PR> [--repo owner/name] [--json] [--no-codeowners]

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

The false-PARTIAL trap (why per-file CODEOWNERS resolution matters)
-------------------------------------------------------------------
A CODEOWNERS line lists a *set* of owners, and under GitHub semantics **one
approval from anyone on the governing line satisfies the code-owner requirement
for that file**. GitHub still auto-requests the *other* owners on the same line,
and they linger in `reviewRequests` as "still requested" even though they are
NOT separately required. A naive "there are approvals AND there are still
outstanding reviewers => PARTIAL" rule therefore *falsely blocks* a PR whose code
review is actually complete.

Real incident (rocm-systems #7125, 2026-09): all changed files were governed by
the single CODEOWNERS line
  /projects/rocr-runtime/  @kentrussell @dayatsin-amd @cfreeamd @atgutier @shwetagkhatri
dayatsin-amd and cfreeamd (both on that line) approved, so `reviewDecision` was
null (satisfied, not REVIEW_REQUIRED). The three others stayed auto-requested.
The old flat rule called it PARTIAL and would have wrongly routed it back to
CODEOWNERS. (The PR was still correctly refused -- but for a *build break*, on the
CI axis, not the review axis.)

What it does
------------
Pulls `reviewDecision`, `latestOpinionatedReviews` (each reviewer's final stance)
and `reviewRequests` (still-outstanding required reviewers, incl. CODEOWNERS
teams). When `reviewDecision` is empty and there are approvals but still-requested
owners, it does a **per-file CODEOWNERS resolution**: it fetches the PR's changed
files and the repo CODEOWNERS, finds each file's governing rule (last match wins,
GitHub semantics), and checks whether an approver already satisfies that rule
(directly as a user owner, or as a member of a team owner). If every changed file
is covered, the still-requested names are same-line alternates and the verdict is
upgraded from PARTIAL to APPROVED. Verdicts:

  APPROVED          reviewDecision == APPROVED, or (decision empty AND >=1
                    standing approval AND no changes-requested AND either no
                    outstanding codeowner requests OR per-file CODEOWNERS
                    resolution shows every changed file is already covered)
  CHANGES_REQUESTED a reviewer's latest stance is CHANGES_REQUESTED  -> hard stop
  PARTIAL           there ARE standing approvals but at least one changed file's
                    governing CODEOWNERS rule is still unsatisfied (or CODEOWNERS
                    could not be resolved) -> code review is NOT complete; route
                    the remaining owners, do NOT bypass review
  NOT_APPROVED      reviewDecision == REVIEW_REQUIRED, or no standing approval

Exit codes: 0 APPROVED, 2 PARTIAL, 3 NOT_APPROVED, 4 CHANGES_REQUESTED, 1 error.

IMPORTANT: a gardener bypass is for known-infra/flaky *CI*, never for unmet code
review. Only APPROVED is bypass-eligible on the review axis; PARTIAL / NOT_APPROVED
/ CHANGES_REQUESTED all route to CODEOWNERS. Even when this helper returns
APPROVED, the CI axis is separate: a failing *build/compile* required gate is
never bypassable (see the skill's Hard rule).
"""
import argparse, base64, json, re, subprocess, sys


def _gh(args):
    p = subprocess.run(["gh"] + args, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode("utf-8", "replace")[:800] or "gh failed")
    return p.stdout.decode("utf-8", "replace")


def gql(repo_owner, repo_name, pr):
    q = """query($o:String!,$n:String!,$pr:Int!){
      repository(owner:$o,name:$n){pullRequest(number:$pr){
        reviewDecision
        reviewRequests(first:50){nodes{requestedReviewer{
          __typename ... on User{login} ... on Team{name slug}}}}
        latestOpinionatedReviews(first:50){nodes{author{login} state authorAssociation}}
      }}}"""
    out = _gh(["api", "graphql", "-f", "query=" + q,
               "-F", "o=" + repo_owner, "-F", "n=" + repo_name, "-F", "pr=%d" % pr])
    return json.loads(out)["data"]["repository"]["pullRequest"]


# ---------------------------------------------------------------------------
# CODEOWNERS resolution
# ---------------------------------------------------------------------------
_CO_PATHS = [".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"]


def fetch_codeowners(repo):
    for path in _CO_PATHS:
        try:
            out = _gh(["api", "repos/%s/contents/%s" % (repo, path)])
        except Exception:
            continue
        try:
            content = json.loads(out).get("content", "")
        except Exception:
            continue
        if content:
            try:
                return base64.b64decode(content).decode("utf-8", "replace")
            except Exception:
                continue
    return None


def changed_files(repo, pr):
    try:
        out = _gh(["api", "repos/%s/pulls/%d/files" % (repo, pr),
                   "--paginate", "--jq", ".[].filename"])
    except Exception:
        return []
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def parse_codeowners(text):
    """Return an ordered list of (pattern, [owners]) tuples."""
    rules = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # strip trailing inline comments
        if " #" in line:
            line = line.split(" #", 1)[0].strip()
        parts = line.split()
        if len(parts) < 2:
            continue
        pattern, owners = parts[0], [o for o in parts[1:] if o.startswith("@")]
        if owners:
            rules.append((pattern, owners))
    return rules


def _translate(pat):
    out, i, n = [], 0, len(pat)
    while i < n:
        c = pat[i]
        if c == "*":
            if i + 1 < n and pat[i + 1] == "*":
                out.append(".*")
                i += 2
                if i < n and pat[i] == "/":
                    i += 1
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(c))
        i += 1
    return "".join(out)


def co_match(pattern, path):
    p = pattern
    lead = p.startswith("/")
    p = p.strip("/")
    if not p:
        return True  # bare '/' matches everything
    anchored = lead or ("/" in p)
    body = _translate(p)
    regex = ("^" if anchored else "(?:^|.*/)") + body + r"(?:/.*)?$"
    return re.match(regex, path) is not None


def governing_owners(path, rules):
    """GitHub semantics: the LAST matching pattern wins."""
    owners = None
    for pattern, os_ in rules:
        if co_match(pattern, path):
            owners = os_
    return owners


_team_cache = {}


def team_members(org, slug):
    key = (org, slug)
    if key in _team_cache:
        return _team_cache[key]
    try:
        out = _gh(["api", "orgs/%s/teams/%s/members" % (org, slug),
                   "--paginate", "--jq", ".[].login"])
        members = {ln.strip().lower() for ln in out.splitlines() if ln.strip()}
    except Exception:
        members = None  # unresolved (no permission / not found)
    _team_cache[key] = members
    return members


def rule_satisfied(owners, approvals_lower):
    """A rule is satisfied if ANY listed owner is covered by an approval.
    Returns (satisfied_bool, unresolved_team_list)."""
    unresolved = []
    for o in owners:
        name = o.lstrip("@")
        if "/" in name:  # team owner @org/slug
            org, slug = name.split("/", 1)
            members = team_members(org, slug)
            if members is None:
                unresolved.append(o)
                continue
            if approvals_lower & members:
                return True, unresolved
        else:  # user owner @login
            if name.lower() in approvals_lower:
                return True, unresolved
    return False, unresolved


def codeowners_refine(repo, pr, approvals):
    """Per-file CODEOWNERS resolution. Returns dict or None if unresolvable."""
    text = fetch_codeowners(repo)
    files = changed_files(repo, pr)
    if not text or not files:
        return None
    rules = parse_codeowners(text)
    if not rules:
        return None
    approvals_lower = {a.lower() for a in approvals}
    unsatisfied, unresolved = {}, set()
    for f in files:
        owners = governing_owners(f, rules)
        if not owners:
            continue  # no code owner for this file -> not review-blocking
        ok, unres = rule_satisfied(owners, approvals_lower)
        if not ok:
            unsatisfied[f] = owners
            unresolved.update(unres)
    return {
        "satisfied": len(unsatisfied) == 0,
        "unsatisfied": unsatisfied,
        "unresolvedTeams": sorted(unresolved),
        "filesChecked": len(files),
    }


def classify(pr_data, repo=None, pr=None, use_codeowners=True):
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

    codeowners = None
    note = None
    if changes or decision == "CHANGES_REQUESTED":
        verdict = "CHANGES_REQUESTED"
    elif decision == "APPROVED":
        verdict = "APPROVED"
    elif decision == "REVIEW_REQUIRED":
        verdict = "NOT_APPROVED"
    else:  # decision is None/'' -> disambiguate from reviews + outstanding requests
        if approvals and not pending:
            verdict = "APPROVED"
        elif approvals and pending:
            verdict = "PARTIAL"
            # per-file CODEOWNERS resolution: are the still-requested owners just
            # same-line alternates on already-satisfied rules?
            if use_codeowners and repo and pr:
                codeowners = codeowners_refine(repo, pr, approvals)
                if codeowners and codeowners["satisfied"]:
                    verdict = "APPROVED"
                    note = ("code-owner review satisfied per-file: every changed "
                            "file is covered by an approval; the still-requested "
                            "reviewers are same-line alternates on already-satisfied "
                            "CODEOWNERS rules and are not separately required.")
                elif codeowners and codeowners["unresolvedTeams"]:
                    note = ("could not resolve membership of team(s): "
                            + ", ".join(codeowners["unresolvedTeams"])
                            + " -- verify manually before treating as APPROVED.")
        else:
            verdict = "NOT_APPROVED"

    return {
        "reviewDecision": decision,
        "verdict": verdict,
        "approvals": approvals,
        "changesRequestedBy": changes,
        "outstandingReviewers": pending,
        "codeowners": codeowners,
        "note": note,
    }


EXIT = {"APPROVED": 0, "PARTIAL": 2, "NOT_APPROVED": 3, "CHANGES_REQUESTED": 4}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pr", type=int)
    ap.add_argument("--repo", default="ROCm/rocm-systems")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-codeowners", action="store_true",
                    help="skip per-file CODEOWNERS resolution of a null-decision PARTIAL")
    a = ap.parse_args()
    owner, name = a.repo.split("/", 1)
    try:
        data = gql(owner, name, a.pr)
    except Exception as e:
        print("ERROR:", e, file=sys.stderr)
        return 1
    r = classify(data, repo=a.repo, pr=a.pr, use_codeowners=not a.no_codeowners)
    if a.json:
        print(json.dumps(r, indent=1))
    else:
        print("PR #%d  reviewDecision=%r  -> %s" % (a.pr, r["reviewDecision"], r["verdict"]))
        if r["approvals"]:
            print("  approved by:", ", ".join(r["approvals"]))
        if r["changesRequestedBy"]:
            print("  CHANGES requested by:", ", ".join(r["changesRequestedBy"]))
        if r["outstandingReviewers"]:
            print("  still-requested reviewers:", ", ".join(r["outstandingReviewers"]))
        co = r.get("codeowners")
        if co and co.get("unsatisfied"):
            print("  changed files still missing a code-owner approval:")
            for f, owners in co["unsatisfied"].items():
                print("    %s  (owners: %s)" % (f, " ".join(owners)))
        if r.get("note"):
            print("  NOTE:", r["note"])
        if r["verdict"] == "PARTIAL":
            print("  PARTIAL: code review is NOT complete; route the remaining owners.")
            print("           This is NOT a review-bypass case.")
        elif r["verdict"] == "APPROVED" and co:
            print("  (upgraded from a flat PARTIAL via per-file CODEOWNERS resolution.)")
    return EXIT[r["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
