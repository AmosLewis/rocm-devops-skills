#!/usr/bin/env python3
r"""Emit the gardener merge-override verdict report table.

When a gardener is asked to *process a batch* of override requests ("process
these", "/process-merge-override" over several PRs, or a fresh sweep), this
renders one markdown row per OPEN request PR with:

  PR (GitHub link) | Repo | Requester | Verdict | Reason | Teams (discussion link)

It joins two sources:
  - a verdicts JSON  : [{pr, repo, requester, verdict, note}, ...]
      (dump the SKILL's `ovr`-style triage table, or write it by hand)
  - a gardener report: the teams-gardener-requests `--json` output (report_now.json)
      used only to look up each PR's GitHub url + live state and the Teams
      `l/message` permalink for the request post.

Both PR link and Teams link are REQUIRED in the output — never drop the Teams
permalink when summarizing (see teams-gardener-requests skill).

Usage:
  python build_verdict_report.py --verdicts verdicts.json \
      --report ..\..\teams-gardener-requests\scripts\report_now.json \
      --md verdict_report.md

If --report is omitted the table still renders with plain PR links and a blank
Teams cell (a warning is printed) so the report degrades gracefully.
"""
import argparse
import json
import sys

# verdict -> (emoji, sort rank) : eligible first, blocked/cannot last.
VERDICT_ORDER = {
    "ELIGIBLE": (0, "\u2705"),
    "ELIGIBLE-after": (1, "\U0001f553"),
    "ELIGIBLE-caveat": (2, "\u26a0\ufe0f"),
    "BLOCKED": (3, "\u26d4"),
    "CANNOT": (4, "\u26d4"),
    "NOT-bypass": (5, "\U0001f6ab"),
}


def rank(verdict: str):
    v = (verdict or "").strip()
    for key, (r, emoji) in VERDICT_ORDER.items():
        if v.upper().startswith(key.upper()):
            return r, emoji
    return 9, ""


def load_report_index(path):
    """Map (repo_short, pr_number) -> {url, state, teams} from a gardener report."""
    idx = {}
    if not path:
        return idx
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"WARN: could not read report {path}: {e}", file=sys.stderr)
        return idx
    for cname, ch in d.get("channels", {}).items():
        for r in ch.get("requests", []):
            for p in r.get("prs", []):
                gh = p.get("gh") or {}
                num = str(p.get("number"))
                # key by the PR's OWN repo, not the channel it was posted in
                # (a rocm-libraries PR can be asked about in the systems channel)
                prepo = (p.get("repo") or "").replace("ROCm/", "").strip()
                url = gh.get("url") or f"https://github.com/{p.get('repo')}/pull/{num}"
                key = (prepo, num)
                # keep the earliest post's teams link; don't overwrite
                idx.setdefault(key, {
                    "url": url,
                    "state": gh.get("state", ""),
                    "teams": r.get("teamsLink", ""),
                })
    return idx


def esc(s):
    return (s or "").replace("|", "\\|").replace("\n", " ")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verdicts", required=True, help="verdicts JSON [{pr,repo,requester,verdict,note}]")
    ap.add_argument("--report", help="teams-gardener-requests report_now.json for PR + Teams links")
    ap.add_argument("--md", help="also write the markdown to this path")
    args = ap.parse_args()

    verdicts = json.load(open(args.verdicts, encoding="utf-8"))
    idx = load_report_index(args.report)
    if args.report and not idx:
        print("WARN: report had no PRs; Teams links will be blank", file=sys.stderr)

    rows = []
    for v in verdicts:
        repo = (v.get("repo") or "").replace("ROCm/", "").strip()
        num = str(v.get("pr"))
        info = idx.get((repo, num), {})
        url = info.get("url") or f"https://github.com/ROCm/{repo}/pull/{num}"
        teams = info.get("teams", "")
        r, emoji = rank(v.get("verdict"))
        rows.append({
            "rank": r, "emoji": emoji, "repo": repo, "num": num, "url": url,
            "verdict": v.get("verdict", ""), "note": v.get("note", ""),
            "requester": v.get("requester", ""), "state": info.get("state", ""),
            "teams": teams,
        })
    rows.sort(key=lambda x: (x["rank"], x["repo"], int(x["num"])))

    out = []
    out.append("## Open merge-override asks — verdicts\n")
    out.append("| PR | Repo | Requester | State | Verdict | Reason | Teams |")
    out.append("|----|------|-----------|-------|---------|--------|-------|")
    missing = []
    for x in rows:
        pr = f"[#{x['num']}]({x['url']})"
        teams = f"[message]({x['teams']})" if x["teams"] else ""
        if not x["teams"]:
            missing.append(x["num"])
        verdict = f"{x['emoji']} {esc(x['verdict'])}".strip()
        out.append(
            f"| {pr} | {esc(x['repo'])} | {esc(x['requester'])} | {esc(x['state'])} | "
            f"{verdict} | {esc(x['note'])} | {teams} |"
        )
    md = "\n".join(out)
    print(md)
    if missing:
        print(f"\nWARN: no Teams link for PR(s): {', '.join(missing)} "
              "(re-run teams-gardener-requests to refresh report_now.json)",
              file=sys.stderr)
    if args.md:
        open(args.md, "w", encoding="utf-8").write(md + "\n")
        print(f"\nwrote {args.md}", file=sys.stderr)


if __name__ == "__main__":
    main()
