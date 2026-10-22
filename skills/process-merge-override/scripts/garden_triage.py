#!/usr/bin/env python3
r"""
garden_triage.py - "Common vs distinctive" failure triage across one or more PRs.

Gathers every failing leaf job across the PRs, then splits them into
  * COMMON      - the same job fails across multiple PRs regardless of the diff
                  => environment / infra flake, not caused by any one code change
  * DISTINCTIVE - a job that fails on only one PR
                  => inspect closely; could be the diff. --deep reads its first
                     failing step to hint infra (checkout/fetch/setup death,
                     timeout gap) vs code (CMake/compile/test assertion).

Aggregator jobs ("* CI Summary", "Output failed jobs", notifiers) are excluded so
the count reflects real leaf failures, not roll-ups.

Read-only. Examples:
  # single PRs triaged together (shared infra shows up as COMMON):
  python garden_triage.py --prs 10000,10802,10396 --repo ROCm/rocm-systems
  # a stack, with first-failing-step hints:
  python garden_triage.py --prs 10011,10012,10210 --repo ROCm/rocm-systems --deep
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime


def gh_json(path):
    """gh api <path> -> parsed JSON object (single page)."""
    p = subprocess.run(["gh", "api", path], capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode("utf-8", "replace")[:800] or "gh api failed")
    return json.loads(p.stdout.decode("utf-8", "replace"))


def gh_jsonl(path, jq):
    """gh api <path> --paginate --jq <jq> -> list of parsed JSON lines."""
    p = subprocess.run(["gh", "api", path, "--paginate", "--jq", jq], capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode("utf-8", "replace")[:800] or "gh api failed")
    out = p.stdout.decode("utf-8", "replace")
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def normalize(name):
    """Collapse shard/attempt/matrix noise so the same lane groups together."""
    n = re.sub(r"\(shard \d+ of \d+\)", "", name)
    n = re.sub(r"\([^)]*\|\s*([^)]+)\)", r"(\1)", n)  # (comp,comp | gfx94X-dcgpu) -> (gfx94X-dcgpu)
    n = re.sub(r"\s+", " ", n).strip()
    return n.rstrip("/").strip()


def is_aggregator(name):
    return bool(re.search(r"CI Summary$|Output failed jobs|Evaluate workflow results|notify|Notify", name))


def step_hint(repo, job_id):
    """Cheap infra-vs-code hint from the first failing step."""
    j = gh_json("repos/%s/actions/jobs/%s" % (repo, job_id))
    bad = next((s for s in j.get("steps", [])
                if s.get("conclusion") not in ("success", "skipped", None)), None)
    if not bad:
        return "no-failed-step (cancelled/zero-signal)"
    s = bad.get("name", "")
    if re.search(r"Set up job|Fetch sources|checkout|container|Driver|GPU sanity|download|Prepare", s):
        return "infra? step='%s'" % s
    if re.search(r"Build|CMake|Compile|Test|cmake", s):
        dur = None
        if bad.get("started_at") and bad.get("completed_at"):
            try:
                a = datetime.fromisoformat(bad["started_at"].replace("Z", "+00:00"))
                b = datetime.fromisoformat(bad["completed_at"].replace("Z", "+00:00"))
                dur = int((b - a).total_seconds() // 60)
            except ValueError:
                dur = None
        if dur is not None and 29 <= dur <= 31:
            return "infra? step='%s' (~%dmin timeout gap)" % (s, dur)
        return "code? step='%s'" % s
    return "inspect step='%s'" % s


def parse_prs(values):
    prs = []
    for v in values:
        for part in str(v).split(","):
            part = part.strip()
            if part:
                prs.append(int(part))
    return prs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prs", nargs="+", required=True,
                    help="PR numbers, space- or comma-separated (e.g. --prs 10000,10802 10396)")
    ap.add_argument("--repo", default="ROCm/rocm-systems")
    ap.add_argument("--workflow", default="TheRock CI")
    ap.add_argument("--deep", action="store_true",
                    help="read each distinctive job's first failing step for an infra-vs-code hint")
    a = ap.parse_args()
    prs = parse_prs(a.prs)

    # 1. Collect failing leaf jobs per PR
    rows = []  # (pr, normalized_job, job_id, run_id)
    for pr in prs:
        sha = gh_json("repos/%s/pulls/%d" % (a.repo, pr))["head"]["sha"]
        runs = gh_jsonl("repos/%s/actions/runs?head_sha=%s&per_page=100" % (a.repo, sha),
                        ".workflow_runs[] | {id,name,created_at}")
        wf = [r for r in runs if r["name"] == a.workflow]
        if not wf:
            print("WARNING #%d: no '%s' run on %s" % (pr, a.workflow, sha[:10]), file=sys.stderr)
            continue
        run = sorted(wf, key=lambda r: r["created_at"])[-1]
        jobs = gh_jsonl("repos/%s/actions/runs/%s/jobs?per_page=100" % (a.repo, run["id"]),
                        ".jobs[] | {id,name,conclusion}")
        for j in jobs:
            if j.get("conclusion") != "failure" or is_aggregator(j["name"]):
                continue
            rows.append((pr, normalize(j["name"]), j["id"], run["id"]))

    if not rows:
        print("No leaf job failures found across: %s" % ", ".join(str(p) for p in prs))
        return 0

    # 2. Group by normalized job name; COMMON = appears on >1 PR
    groups = {}
    for pr, job, job_id, run_id in rows:
        g = groups.setdefault(job, {"prs": set(), "sample_job_id": job_id})
        g["prs"].add(pr)
    grouped = []
    for job, g in groups.items():
        pr_list = sorted(g["prs"])
        grouped.append({"job": job, "prs": pr_list, "count": len(pr_list),
                        "kind": "COMMON" if len(pr_list) > 1 else "DISTINCTIVE",
                        "sample_job_id": g["sample_job_id"]})
    grouped.sort(key=lambda x: (x["kind"] != "COMMON", -x["count"], x["job"]))

    print("\n===== COMMON failures (same lane across >1 PR => environment/infra, not diff) =====")
    common = [g for g in grouped if g["kind"] == "COMMON"]
    if common:
        for g in common:
            print("  %d PRs  #%s  %s" % (g["count"], ",".join(str(p) for p in g["prs"]), g["job"]))
    else:
        print("  (none)")

    print("\n===== DISTINCTIVE failures (single PR => inspect for a code cause) =====")
    distinct = [g for g in grouped if g["kind"] == "DISTINCTIVE"]
    if distinct:
        for g in distinct:
            line = "  #%s  %s" % (",".join(str(p) for p in g["prs"]), g["job"])
            if a.deep:
                line += "  ->  " + step_hint(a.repo, g["sample_job_id"])
            print(line)
    else:
        print("  (none)")

    print("\n----- verdict aid -----")
    print("  COMMON lanes are shared infra/environment noise (rule out the diff).")
    print("  DISTINCTIVE lanes are the ones to justify: --deep hints infra vs code from the first failing step,")
    print("  but the final infra-vs-code call is the gardener's (read the log, not just the step name).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
