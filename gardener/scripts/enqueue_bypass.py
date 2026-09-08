"""Bypass-merge one stacked PR by driving the authenticated CDP browser's own
`page_data/enqueue_stack` call (the exact request the web "bypass rules" checkbox sends).

Usage:  python enqueue_bypass.py <PR> [--go]
Without --go it is a DRY RUN: it fetches and prints the merge defaults and confirms the PR is the
current bottom of the stack (base=develop, OPEN), but does NOT enqueue.
With --go it performs the irreversible bypass merge and polls until it resolves.
"""
import sys, time, json, subprocess
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pychrome
import urllib.request

REPO_OWNER, REPO_NAME = "ROCm", "rocm-systems"
AUTHOR_EMAIL = "you@example.com"   # the merging user's email, as captured from the UI
CDP = "http://127.0.0.1:9222"

def gh_token():
    return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()

def graphql(token, query):
    data = json.dumps({"query": query}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=data,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "enqueue-bypass"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def get_defaults(token, pr):
    q = ('query{repository(owner:"%s",name:"%s"){pullRequest(number:%d){'
         'title state baseRefName headRefName mergeStateStatus '
         'viewerMergeHeadlineText(mergeType:MERGE) viewerMergeBodyText(mergeType:MERGE)}}}'
         % (REPO_OWNER, REPO_NAME, pr))
    d = graphql(token, q)
    return d["data"]["repository"]["pullRequest"]

def main():
    if len(sys.argv) < 2:
        print("usage: enqueue_bypass.py <PR> [--go]"); return 2
    pr = int(sys.argv[1])
    go = "--go" in sys.argv

    tok = gh_token()
    p = get_defaults(tok, pr)
    print(f"PR #{pr}: {p['title']}")
    print(f"  state={p['state']} base={p['baseRefName']} mergeState={p['mergeStateStatus']}")
    headline = p["viewerMergeHeadlineText"]
    body = p["viewerMergeBodyText"] or ""
    print(f"  commitTitle : {headline}")
    print(f"  commitBody  : {len(body)} chars, first line: {body.splitlines()[0] if body else ''}")

    if p["state"] != "OPEN":
        print("  ! PR is not OPEN - refusing."); return 1
    if p["baseRefName"] != "develop":
        print(f"  ! base is '{p['baseRefName']}', not develop - this is NOT the current bottom of the "
              f"stack yet. Merge the PR below it first."); return 1

    if not go:
        print("\nDRY RUN - pass --go to enqueue the bypass merge.")
        return 0

    payload = {"authorEmail": AUTHOR_EMAIL, "commitMessage": body, "commitTitle": headline,
               "mergeMethod": "MERGE", "bypassRules": "true"}

    url = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/pull/{pr}"
    browser = pychrome.Browser(url=CDP)
    tab = browser.new_tab(url=url)
    tab.start(); tab.Page.enable(); tab.Runtime.enable()

    # Poll for a hydrated, logged-in page: a non-empty fetch-nonce AND a user-login meta.
    # A fixed sleep is unreliable - a cold tab can take >9s, yielding an empty nonce and a 404.
    nonce, login = "", ""
    for _ in range(20):  # up to ~40s
        time.sleep(2)
        login = tab.Runtime.evaluate(expression=
            "(document.querySelector('meta[name=\"user-login\"]')||{}).content||''",
            returnByValue=True)["result"]["value"]
        nonce = tab.Runtime.evaluate(expression=
            "(document.querySelector('meta[name=\"fetch-nonce\"]')||{}).content||''",
            returnByValue=True)["result"]["value"]
        if nonce and login:
            break
    print(f"  logged in as: {login or '(none)'}  fetch-nonce: {nonce[:20]}{'...' if nonce else '(EMPTY)'}")
    if not nonce or not login:
        print("  ! page did not hydrate a logged-in GitHub session (empty nonce/login). "
              "Confirm the CDP Chrome is signed into GitHub, then retry."); tab.stop(); return 1

    js = r"""
    (async (payload) => {
      const base = location.pathname.replace(/\/$/,'');
      const nonce = () => (document.querySelector('meta[name="fetch-nonce"]')||{}).content||'';
      // Arm/refresh the verified-fetch context with a GET the app normally issues first.
      try {
        await fetch(base + '/page_data/merge_box?merge_method=MERGE&bypass_requirements=true',
          {credentials:'include', headers:{'X-Requested-With':'XMLHttpRequest',
           'GitHub-Verified-Fetch':'true','X-Fetch-Nonce':nonce()}});
      } catch (e) {}
      // Read the nonce FRESH immediately before the POST (it is single-use / rotates).
      const u = base + '/page_data/enqueue_stack';
      const r = await fetch(u, {method:'POST', credentials:'include',
        headers:{'X-Requested-With':'XMLHttpRequest','GitHub-Verified-Fetch':'true',
                 'X-Fetch-Nonce':nonce(),'Content-Type':'application/json'},
        body: JSON.stringify(payload)});
      const t = await r.text();
      return JSON.stringify({status:r.status, body:t});
    })(%s)
    """ % json.dumps(payload)
    res = tab.Runtime.evaluate(expression=js, awaitPromise=True, returnByValue=True)
    out = json.loads(res["result"]["value"])
    print("  enqueue:", out["status"], out["body"][:300])
    try:
        enq = json.loads(out["body"])
    except Exception:
        enq = {}
    uuid = enq.get("uuid")
    if out["status"] not in (200, 202) or not uuid:
        print("  ! enqueue did not return a uuid - aborting poll."); tab.stop(); return 1

    # Poll the status endpoint from the page context until it stops being 'pending'.
    for i in range(40):
        time.sleep(3)
        pjs = r"""
        (async (uuid) => {
          const u = location.pathname.replace(/\/$/,'') + '/page_data/merge_request_status/' + uuid;
          const r = await fetch(u, {credentials:'include',
            headers:{'X-Requested-With':'XMLHttpRequest','GitHub-Verified-Fetch':'true'}});
          return await r.text();
        })(%s)
        """ % json.dumps(uuid)
        st = tab.Runtime.evaluate(expression=pjs, awaitPromise=True, returnByValue=True)["result"]["value"]
        try:
            sj = json.loads(st)
        except Exception:
            sj = {"raw": st[:200]}
        print(f"  poll[{i}]: {sj}")
        if sj.get("status") and sj.get("status") != "pending":
            break
    tab.stop()

    # Confirm merged state via GraphQL.
    time.sleep(3)
    p2 = get_defaults(tok, pr)
    print(f"  FINAL: state={p2['state']}")
    return 0 if p2["state"] == "MERGED" else 1

if __name__ == "__main__":
    sys.exit(main())
