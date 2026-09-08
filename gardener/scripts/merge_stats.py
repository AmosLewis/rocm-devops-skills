#!/usr/bin/env python3
"""Merge statistics for a gardener rotation, per repo.

For each repo it counts, over the merged-window, how many PRs were merged **by
the gardener account** (an admin/override / manual merge) versus merged normally
(auto-merge or a maintainer squash), and reports the current count of OPEN PRs.

This is the "manually merged vs. merges that were not overridden" stat for the
end-of-rotation handover (the number Laura used to produce by hand), plus the
unmerged/open backlog size.

Data source is the GitHub GraphQL search API via `gh api graphql`, paginated, so
`mergedBy` is authoritative (no per-PR REST fan-out).

Usage:
  python merge_stats.py --repos ROCm/rocm-systems ROCm/rocm-libraries \
      --since 2026-08-24 --until 2026-09-01 --gardener <your-github-login> [--json out.json]
"""
import argparse
import json
import subprocess
import sys

GQL = """
query($q: String!, $cursor: String) {
  search(query: $q, type: ISSUE, first: 100, after: $cursor) {
    issueCount
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on PullRequest {
        number
        mergedAt
        author { login }
        mergedBy { login }
      }
    }
  }
}
"""


def run_gql(q, cursor):
    args = ["gh", "api", "graphql", "-f", "query=" + GQL, "-F", "q=" + q]
    if cursor:
        args += ["-F", "cursor=" + cursor]
    out = subprocess.run(args, capture_output=True)
    if out.returncode != 0:
        sys.stderr.write(out.stderr.decode("utf-8", "replace"))
        raise SystemExit("gh api graphql failed")
    return json.loads(out.stdout.decode("utf-8", "replace"))["data"]["search"]


def search_all(q):
    nodes, cursor = [], None
    while True:
        page = run_gql(q, cursor)
        nodes.extend(n for n in page["nodes"] if n)
        if not page["pageInfo"]["hasNextPage"]:
            return nodes, page["issueCount"]
        cursor = page["pageInfo"]["endCursor"]


def open_count(repo):
    q = "repo:%s is:pr is:open" % repo
    page = run_gql(q, None)
    return page["issueCount"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos", nargs="+", required=True)
    ap.add_argument("--since", required=True, help="merged-at start, YYYY-MM-DD")
    ap.add_argument("--until", required=True, help="merged-at end, YYYY-MM-DD")
    ap.add_argument("--gardener", required=True, help="gardener GitHub login")
    ap.add_argument("--json", help="optional path to dump the raw per-repo result")
    args = ap.parse_args()

    report = {"window": "%s..%s" % (args.since, args.until),
              "gardener": args.gardener, "repos": {}}

    print("Merge stats  window=%s..%s  gardener=@%s\n"
          % (args.since, args.until, args.gardener))
    grand = {"manual": 0, "normal": 0, "total": 0}
    for repo in args.repos:
        q = "repo:%s is:pr is:merged merged:%s..%s" % (repo, args.since, args.until)
        nodes, count = search_all(q)
        manual = [n for n in nodes
                  if (n.get("mergedBy") or {}).get("login") == args.gardener]
        normal = [n for n in nodes
                  if (n.get("mergedBy") or {}).get("login") != args.gardener]
        # who else merged (for context)
        others = {}
        for n in normal:
            who = (n.get("mergedBy") or {}).get("login") or "(unknown)"
            others[who] = others.get(who, 0) + 1
        top = sorted(others.items(), key=lambda kv: -kv[1])[:5]
        opn = open_count(repo)

        report["repos"][repo] = {
            "merged_total": len(nodes),
            "manual_override": len(manual),
            "not_overridden": len(normal),
            "manual_pct": round(100.0 * len(manual) / len(nodes), 1) if nodes else 0.0,
            "manual_prs": sorted(n["number"] for n in manual),
            "open_prs": opn,
            "top_other_mergers": top,
        }
        grand["manual"] += len(manual)
        grand["normal"] += len(normal)
        grand["total"] += len(nodes)

        print("== %s" % repo)
        print("  merged in window : %d" % len(nodes))
        print("  manual/override  : %d  (%.1f%%)  by @%s%s"
              % (len(manual),
                 report["repos"][repo]["manual_pct"],
                 args.gardener,
                 ("  -> #" + ", #".join(str(n["number"]) for n in
                  sorted(manual, key=lambda x: x["number"]))) if manual else ""))
        print("  NOT overridden   : %d  (auto-merge / maintainer squash)" % len(normal))
        print("  open now         : %d" % opn)
        if top:
            print("  top other mergers: "
                  + ", ".join("%s x%d" % (w, c) for w, c in top))
        print()

    print("== TOTAL across repos")
    print("  merged: %d  |  manual/override: %d  |  not overridden: %d  |  override share: %.1f%%"
          % (grand["total"], grand["manual"], grand["normal"],
             (100.0 * grand["manual"] / grand["total"]) if grand["total"] else 0.0))
    report["total"] = grand

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print("\nwrote %s" % args.json)


if __name__ == "__main__":
    main()
