#!/usr/bin/env python3
"""
Pull recent gardening requests from the Microsoft Teams web client and emit a
markdown + JSON report, fully automated.

How it works (see teams_gardener_requests_skill.md for the full rationale):
  * Connects to an already-running Chrome/Edge started with --remote-debugging-port,
    finds the authenticated Teams tab, and reads the Teams client's own IndexedDB
    caches (conversation-manager + replychain-manager). No fragile UI clicking.
  * Resolves each configured channel's threadId / groupId / tenantId, then collects
    recent messages (author, timestamp, text, PR links, @mentions).
  * Builds canonical Teams deep links (l/message/{threadId}/{messageId}?...), the
    same permalink "Copy link" produces.
  * Optionally enriches each referenced PR with live GitHub state via `gh`.

Prereqs:
  * pip install pychrome
  * Chrome running with --remote-debugging-port=9222 and signed into Teams
    (use --launch to start it against a persistent profile if it is not running).
  * `gh` authenticated (only needed unless --no-gh).

Usage:
  python pull_gardener_requests.py                    # last 48h, both channels, with gh
  python pull_gardener_requests.py --hours 24
  python pull_gardener_requests.py --no-gh --json out.json --md out.md
  python pull_gardener_requests.py --launch           # start Chrome if CDP is down
  python pull_gardener_requests.py --mention "Last, First"    # flag posts that @-tag this name
                                                              # (omit --mention to auto-detect the
                                                              #  logged-in Teams user)
"""
import argparse, json, os, subprocess, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone

try:
    import pychrome
except ImportError:
    sys.exit("pychrome is required:  pip install pychrome")

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- Configuration (edit for other rotations / tenants) --------------------
CHANNEL_REPOS = {
    "Gardening - rocm-libraries": "ROCm/rocm-libraries",
    "Gardening - rocm-systems":  "ROCm/rocm-systems",
}
DEFAULT_TEAM_NAME = "AIG ROCm"
CDP_URL = "http://127.0.0.1:9222"
CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]
PROFILE_DIR = os.path.expanduser(r"~\.copilot\chrome-cdp-profile")
# ---------------------------------------------------------------------------


def cdp_up():
    try:
        with urllib.request.urlopen(CDP_URL + "/json/version", timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def launch_chrome():
    exe = next((p for p in CHROME_CANDIDATES if os.path.exists(p)), None)
    if not exe:
        sys.exit("No Chrome/Edge executable found; edit CHROME_CANDIDATES.")
    port = urllib.parse.urlparse(CDP_URL).port or 9222
    subprocess.Popen([exe, "--remote-debugging-port=%d" % port,
                      "--user-data-dir=%s" % PROFILE_DIR,
                      "https://teams.microsoft.com/v2/"])
    for _ in range(30):
        time.sleep(2)
        if cdp_up():
            return
    sys.exit("Chrome did not expose the CDP endpoint in time.")


def find_teams_tab(browser):
    for t in browser.list_tab():
        try:
            url = (t._kwargs.get("url") or "") if hasattr(t, "_kwargs") else ""
        except Exception:
            url = ""
        # pychrome Tab exposes url via list_tab dicts; fall back to raw /json/list
        if "teams.microsoft.com" in url:
            return t
    # robust fallback via raw endpoint
    with urllib.request.urlopen(CDP_URL + "/json/list", timeout=5) as r:
        tabs = json.loads(r.read().decode("utf-8"))
    tid = next((t["id"] for t in tabs
                if t.get("type") == "page" and "teams.microsoft.com" in t.get("url", "")), None)
    if not tid:
        sys.exit("No authenticated Teams tab found. Sign into Teams in the CDP browser.")
    return [t for t in browser.list_tab() if t.id == tid][0]


def run_extractor(tab, topics):
    js = open(os.path.join(HERE, "pull_messages.js"), "r", encoding="utf-8").read()
    prelude = "var CHANNEL_TOPICS = %s;\n" % json.dumps(topics)
    tab.start()
    try:
        tab.call_method("Runtime.enable")
        r = tab.call_method("Runtime.evaluate", expression=prelude + js,
                            returnByValue=True, awaitPromise=True)
        val = r.get("result", {}).get("value")
        if val is None:
            exc = r.get("exceptionDetails")
            sys.exit("Extractor returned nothing. %s" % json.dumps(exc)[:500])
        return json.loads(val)
    finally:
        try:
            tab.stop()
        except Exception:
            pass


# --- Optional UI sync: open each channel and scroll to hydrate IndexedDB -----
# CDP Input.dispatchMouseEvent delivers a *trusted* click (isTrusted=true) that
# Teams honours, unlike a JS synthetic click. This path is best-effort: it
# readiness-gates on the "setting things up" splash and hit-tests the target
# before clicking, and simply skips (with a warning) if a channel can't be hit.

_SPLASH_SEL = '[class*="fade-out-animation"]'


def _eval(tab, js):
    r = tab.call_method("Runtime.evaluate", expression=js,
                        returnByValue=True, awaitPromise=True)
    if r.get("exceptionDetails"):
        return None
    return r.get("result", {}).get("value")


def _trusted_click(tab, x, y):
    tab.call_method("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
    time.sleep(0.05)
    tab.call_method("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y,
                    button="left", buttons=1, clickCount=1)
    time.sleep(0.06)
    tab.call_method("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y,
                    button="left", buttons=0, clickCount=1)


def _wait_ready(tab, timeout=20.0):
    """Wait until the full-viewport loading splash is gone."""
    deadline = time.time() + timeout
    js = "!document.querySelector('%s')" % _SPLASH_SEL
    while time.time() < deadline:
        if _eval(tab, js) is True:
            return True
        time.sleep(1.0)
    return False


def _locate_channel(tab, topic):
    """Return {x,y,hittable} for a channel's left-nav tree item, or None."""
    js = r"""
    (function(){
      var t=%s;
      var e=[].slice.call(document.querySelectorAll('div.fui-TreeItemLayout__main'))
            .filter(function(x){return (x.textContent||'').trim()===t && x.offsetParent;})[0];
      if(!e) return null;
      e.scrollIntoView({block:'center'});
      var r=e.getBoundingClientRect(); var cx=r.left+r.width/2, cy=r.top+r.height/2;
      var at=document.elementFromPoint(cx,cy);
      return JSON.stringify({x:Math.round(cx),y:Math.round(cy),
        hittable: at ? (e.contains(at)||e===at) : false});
    })()
    """ % json.dumps(topic)
    val = _eval(tab, js)
    if not val:
        return None
    try:
        return json.loads(val)
    except Exception:
        return None


def _scroll_pane(tab, times, pause):
    js = r"""
    (async function(){
      function q(){return document.querySelector('[data-tid="message-pane-list-viewport"]');}
      var last=null;
      for(var i=0;i<%d;i++){
        var v=q(); if(!v) break;
        last=v.scrollHeight; v.scrollTop=0;
        await new Promise(function(r){setTimeout(r,%d);});
      }
      var v2=q(); return v2 ? v2.scrollHeight : last;
    })()
    """ % (int(times), int(pause * 1000))
    return _eval(tab, js)


def sync_channels(tab, topics, scrolls=6, pause=1.8):
    """Best-effort: open each channel via a trusted click and scroll up to load
    older chains into IndexedDB. Prints a short status line per channel."""
    tab.start()
    try:
        tab.call_method("Runtime.enable")
        if not _wait_ready(tab):
            sys.stderr.write("[sync] Teams still on a loading splash; skipping UI sync.\n")
            return
        for topic in topics:
            loc = None
            for _ in range(3):
                loc = _locate_channel(tab, topic)
                if loc and loc.get("hittable"):
                    break
                time.sleep(1.0)
            if not (loc and loc.get("hittable")):
                sys.stderr.write("[sync] %s: channel item not hittable; skipped.\n" % topic)
                continue
            _trusted_click(tab, loc["x"], loc["y"])
            time.sleep(3.0)
            sh = _scroll_pane(tab, scrolls, pause)
            sys.stderr.write("[sync] %s: opened + scrolled (viewport ~%s px).\n" % (topic, sh))
        time.sleep(2.0)  # let the client flush loaded chains into IndexedDB
    finally:
        try:
            tab.stop()
        except Exception:
            pass



def teams_link(ch, msg_id, parent_id, team_name):
    qs = {
        "tenantId": ch.get("tenant") or "",
        "groupId": ch.get("groupId") or "",
        "parentMessageId": parent_id,
        "createdTime": msg_id,
    }
    if team_name:
        qs["teamName"] = team_name
    qs = {k: v for k, v in qs.items() if v}
    thread = urllib.parse.quote(ch["threadId"], safe="")
    return "https://teams.microsoft.com/l/message/%s/%s?%s" % (
        thread, msg_id, urllib.parse.urlencode(qs))


def gh_state(repo, number, cache):
    key = (repo, number)
    if key in cache:
        return cache[key]
    try:
        out = subprocess.run(
            ["gh", "pr", "view", str(number), "--repo", repo, "--json",
             "number,state,mergeStateStatus,reviewDecision,title,url,isDraft"],
            capture_output=True, text=True, timeout=40)
        data = json.loads(out.stdout) if out.stdout.strip().startswith("{") else {"error": out.stderr.strip()[:120]}
    except Exception as e:
        data = {"error": str(e)[:120]}
    cache[key] = data
    return data


def fmt_time(ms):
    try:
        return datetime.fromtimestamp(ms / 1000.0).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ms)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Pull gardening requests from Teams.")
    ap.add_argument("--hours", type=float, default=48.0, help="look-back window (default 48h)")
    ap.add_argument("--launch", action="store_true", help="launch Chrome if CDP is down")
    ap.add_argument("--no-gh", action="store_true", help="skip live GitHub PR state")
    ap.add_argument("--sync", action="store_true",
                    help="before reading, open each channel via a trusted CDP click and "
                         "scroll up to load older messages into IndexedDB (best-effort)")
    ap.add_argument("--sync-scrolls", type=int, default=6,
                    help="how many scroll-to-top passes per channel when --sync (default 6)")
    ap.add_argument("--team-name", default=DEFAULT_TEAM_NAME)
    ap.add_argument("--mention", default=None,
                    help="flag posts that @-mention this display name; if omitted, auto-detect "
                         "the logged-in Teams user")
    ap.add_argument("--json", dest="json_out", default=None, help="write raw JSON report here")
    ap.add_argument("--md", dest="md_out", default=None, help="write markdown report here")
    args = ap.parse_args()

    if not cdp_up():
        if args.launch:
            launch_chrome()
        else:
            sys.exit("CDP endpoint %s is down. Start Chrome with --remote-debugging-port, "
                     "or pass --launch." % CDP_URL)

    browser = pychrome.Browser(url=CDP_URL)
    tab = find_teams_tab(browser)
    if args.sync:
        sync_channels(tab, list(CHANNEL_REPOS.keys()), scrolls=args.sync_scrolls)
        tab = find_teams_tab(browser)  # fresh Tab wrapper (sync stopped the old one)
    result = run_extractor(tab, list(CHANNEL_REPOS.keys()))
    if result.get("error"):
        sys.exit("Extractor error: " + result["error"])

    # Resolve whose @-mentions to flag: an explicit --mention wins, otherwise fall
    # back to the display name of the Teams user currently signed into the browser.
    mention = args.mention or result.get("currentUser")
    if not args.mention:
        if mention:
            print("[mention] auto-detected logged-in Teams user: %s" % mention, file=sys.stderr)
        else:
            print("[mention] could not detect the logged-in user; @-mention flagging disabled",
                  file=sys.stderr)

    now_ms = time.time() * 1000
    cutoff = now_ms - args.hours * 3600 * 1000
    channels_meta = result["channels"]

    # index replies by parent for reply-count / last-reply
    replies = {}
    for m in result["messages"]:
        if not m["isRoot"]:
            replies.setdefault(m["parentId"], []).append(m)

    roots = [m for m in result["messages"] if m["isRoot"] and m["timeMs"] >= cutoff]
    roots.sort(key=lambda m: m["timeMs"])

    gh_cache = {}
    report = {"generatedAt": fmt_time(now_ms), "windowHours": args.hours,
              "mentionName": mention, "channels": {}}
    md = ["# Gardening requests — last %g h (as of %s)\n" % (args.hours, fmt_time(now_ms))]

    for topic, repo in CHANNEL_REPOS.items():
        ch = channels_meta.get(topic)
        if not ch:
            md.append("## %s\n_channel not found in Teams cache_\n" % topic)
            continue
        rows = []
        for m in roots:
            if m["channel"] != topic:
                continue
            kids = replies.get(m["id"], [])
            last_reply = max((k["timeMs"] for k in kids), default=None)
            prs = []
            for pr in m["prs"]:
                repo_full = "%s/%s" % (pr["org"], pr["repo"])
                entry = {"repo": repo_full, "number": pr["number"]}
                if not args.no_gh:
                    entry["gh"] = gh_state(repo_full, pr["number"], gh_cache)
                prs.append(entry)
            tagged = bool(mention and any(mention.lower() in x.lower() for x in m["mentions"]))
            rows.append({
                "author": m["author"], "time": fmt_time(m["timeMs"]),
                "text": m["text"][:200], "prs": prs,
                "replyCount": len(kids),
                "lastReply": fmt_time(last_reply) if last_reply else None,
                "mentions": m["mentions"], "taggedYou": tagged,
                "teamsLink": teams_link(ch, m["id"], m["parentId"], args.team_name),
            })
        report["channels"][topic] = {"repo": repo, "meta": ch, "requests": rows}

        md.append("## %s  (%s)\n" % (topic, repo))
        if not rows:
            md.append("_No requests in the last %g h._\n" % args.hours)
            continue
        md.append("| PR(s) | Requester | When | Replies | State | Teams | Tagged you |")
        md.append("|---|---|---|---|---|---|---|")
        for r in rows:
            pr_cell = "<br>".join(
                "[%s#%s](https://github.com/%s/pull/%s)" % (p["repo"], p["number"], p["repo"], p["number"])
                for p in r["prs"]) or "—"
            state_cell = "<br>".join(
                (p.get("gh", {}) or {}).get("state", "?") + " / " +
                (p.get("gh", {}) or {}).get("mergeStateStatus", "?")
                for p in r["prs"]) if not args.no_gh and r["prs"] else "—"
            reply_cell = "%d%s" % (r["replyCount"], (" (last %s)" % r["lastReply"]) if r["lastReply"] else "")
            md.append("| %s | %s | %s | %s | %s | [message](%s) | %s |" % (
                pr_cell, r["author"], r["time"], reply_cell, state_cell,
                r["teamsLink"], "**YES**" if r["taggedYou"] else ""))
        md.append("")

    md_text = "\n".join(md)
    print(md_text)
    if args.md_out:
        open(args.md_out, "w", encoding="utf-8").write(md_text)
    if args.json_out:
        open(args.json_out, "w", encoding="utf-8").write(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
