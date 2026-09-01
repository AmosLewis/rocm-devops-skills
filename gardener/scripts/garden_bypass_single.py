#!/usr/bin/env python3
r"""
garden_bypass_single.py - Bypass-merge one APPROVED single (non-stacked) PR whose
only required-gate failures are known infra flakes. Posts a rationale comment, then
admin-merges, then verifies. Read-only until --go is passed.

  Single PR  -> gh pr merge --admin            (this script; no browser needed)
  Stacked    -> python enqueue_bypass.py <PR> --go  (CDP; bottom->top; NOT this script)

Example:
  python garden_bypass_single.py 10000 --repo ROCm/rocm-systems \
    --unrelated 'the rocshmem reduce change' \
    --fails 'Linux MI455 Build (gfx125X-dcgpu) / Build Linux Packages: Fetch-sources network timeout' \
    --note '@author: manually verified on <runner label>' \
    --go

Pass one --fails 'Job name: reason' per failing required-gate lane (bullet even a
single one). Wording rules baked in: say "code owner approval" (never name the
owner), "check failures / job failures / errors" (never "reds"), no em dashes,
succinct, "TheRock CI failures are only known infra issues".

HARD RULE: a failing build/compile step is never bypass-eligible unless it is
proven infra. The script refuses if any --fails reason reads as a compile error;
only re-run with --ack-build-failure-is-infra once you have read the build log and
confirmed it died before the compiler ran (fetch/network/toolchain/runner).
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile
import time

COMPILE_PAT = re.compile(
    r"compil|static[ _]assert|undefined reference|\bld:|\blink error\b|cmake error|error:|build failed",
    re.IGNORECASE)


def gh(args, capture=True):
    p = subprocess.run(["gh"] + args, capture_output=capture, text=True)
    return p


def gh_json(args):
    import json
    p = gh(args)
    if p.returncode != 0:
        raise SystemExit("gh %s failed: %s" % (" ".join(args), (p.stderr or "")[:400]))
    return json.loads(p.stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pr", type=int)
    ap.add_argument("--repo", default="ROCm/rocm-systems")
    ap.add_argument("--unrelated", required=True,
                    help='what the failures are unrelated to, e.g. "the one-file rocblit.cpp change"')
    ap.add_argument("--fails", action="append", required=True, metavar="'Job name: reason'",
                    help="one 'Job name: reason' per required-gate failure; repeatable")
    ap.add_argument("--note", default="", help="optional author/owner quote to include")
    ap.add_argument("--method", choices=["merge", "squash", "rebase"], default="merge")
    ap.add_argument("--ack-build-failure-is-infra", action="store_true",
                    help="required to proceed if a reason reads as a compile error (after reading the log)")
    ap.add_argument("--go", action="store_true", help="post the comment and admin-merge (else dry-run)")
    a = ap.parse_args()

    # 1. Gate: must be OPEN + not draft + APPROVED + BLOCKED (a required check failing)
    v = gh_json(["pr", "view", str(a.pr), "--repo", a.repo, "--json",
                 "state,mergeStateStatus,reviewDecision,baseRefName,isDraft"])
    print("PR #%d  state=%s base=%s merge=%s review=%s draft=%s" % (
        a.pr, v.get("state"), v.get("baseRefName"), v.get("mergeStateStatus"),
        v.get("reviewDecision"), v.get("isDraft")))
    if v.get("state") != "OPEN":
        raise SystemExit("not OPEN")
    if v.get("isDraft"):
        raise SystemExit("is DRAFT - author marks ready")

    # Approval detection: reviewDecision alone is NOT reliable (empty even when code
    # owners have approved). check_approval.py resolves the real state; only a true
    # APPROVED is bypass-eligible on the review axis.
    here = os.path.dirname(os.path.abspath(__file__))
    ap_run = subprocess.run([sys.executable, os.path.join(here, "check_approval.py"),
                             str(a.pr), "--repo", a.repo], capture_output=True, text=True)
    for line in (ap_run.stdout or "").splitlines():
        print("  " + line)
    if ap_run.returncode != 0:
        sys.stderr.write(ap_run.stderr or "")
        raise SystemExit("review not fully APPROVED (check_approval verdict rc=%d) - route the "
                         "outstanding code owners; a gardener bypass is for infra/flaky CI, not for "
                         "unmet code review." % ap_run.returncode)

    # 1b. HARD RULE guard: inspect each failure REASON (text after the first ':'),
    # not the job name (job names legitimately contain "Build").
    flagged = []
    for f in a.fails:
        reason = f.split(":", 1)[1] if ":" in f else f
        if COMPILE_PAT.search(reason):
            flagged.append(f.strip())
    if flagged:
        print("\n*** BUILD/COMPILE FAILURE DETECTED in a failure reason ***")
        for f in flagged:
            print("  - " + f)
        print("A failure inside the build/compile step is presumed CODE and is NOT bypass-eligible unless you have")
        print("proven from the build log it died before the compiler ran (fetch/network/toolchain/runner). Do not")
        print("take the author's word that it is 'unrelated' or 'script failures' - open the build log yourself.")
        if not a.ack_build_failure_is_infra:
            raise SystemExit("Refusing to bypass a build/compile failure. If the log truly shows an infra "
                             "cause, re-run with --ack-build-failure-is-infra; otherwise route to CODEOWNERS "
                             "/ get a revert.")
        print("--ack-build-failure-is-infra set: proceeding on your explicit assertion that the build log shows infra.")

    # 2. Build the #10579-style rationale comment
    lines = []
    if a.note:
        lines.append("Will merge given code owner approval and the author's note that")
        lines.append("> " + a.note)
        lines.append("")
    else:
        lines.append("Will merge given code owner approval.")
    lines.append("The TheRock CI failures are only known infra issues, unrelated to %s:" % a.unrelated)
    for f in a.fails:
        job = f.split(":", 1)[0].strip()
        reason = f.split(":", 1)[1].strip() if ":" in f else ""
        lines.append("- `%s`: %s" % (job, reason))
    body = "\n".join(lines).rstrip()
    print("\n--- comment preview ---\n%s\n-----------------------" % body)

    if not a.go:
        print("\nDRY RUN - pass --go to post the comment and admin-merge.")
        return 0

    # 3. Post comment, then admin-merge (bypasses the failing required gate; token auth, no browser)
    tmp = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8")
    try:
        tmp.write(body)
        tmp.close()
        c = gh(["pr", "comment", str(a.pr), "--repo", a.repo, "--body-file", tmp.name])
        if c.returncode != 0:
            raise SystemExit("comment failed: %s" % (c.stderr or "")[:400])
        comment_url = (c.stdout or "").strip()
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
    print("comment posted: " + comment_url)

    m = gh(["pr", "merge", str(a.pr), "--repo", a.repo, "--" + a.method, "--admin"])
    if m.returncode != 0:
        raise SystemExit("admin-merge failed: %s" % (m.stderr or "")[:400])
    time.sleep(3)

    # 4. Verify + emit Teams paste-ready line
    res = gh_json(["pr", "view", str(a.pr), "--repo", a.repo, "--json", "state,mergedBy"])
    print("result: #%d state=%s by=%s" % (a.pr, res.get("state"), (res.get("mergedBy") or {}).get("login")))
    if res.get("state") == "MERGED":
        print("\nTeams reply -> Merged! " + comment_url)
        return 0
    raise SystemExit("merge did not complete - re-check state")


if __name__ == "__main__":
    sys.exit(main())
