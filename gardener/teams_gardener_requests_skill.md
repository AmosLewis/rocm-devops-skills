---
name: teams-gardener-requests
description: Pull recent gardening merge/override/help requests from the Microsoft Teams "Gardening - rocm-libraries" and "Gardening - rocm-systems" channels and produce a table with requester, timestamp, referenced PRs, live GitHub PR state, Teams permalinks, and optional @-mention flagging. Reads the Teams web client's own IndexedDB cache over Chrome CDP (no fragile UI scraping). Use when asked to list/refresh current gardening requests, get Teams discussion links, or check whether you were @-tagged.
---
# Skill: Teams Gardener Requests — automated channel pull

Automates what a monorepo gardener does by hand every few hours: scan the two
gardening channels in Microsoft Teams for merge / override / force-merge / help
requests, cross-reference each to its GitHub PR, and produce a refreshable table
with **Teams discussion permalinks**.

Companion to [`monorepo_gardener_skill.md`](monorepo_gardener_skill.md): this skill
*collects and links* the requests; that skill *triages* each one (`/gr`).

## What it produces

One markdown table per channel, each row = a top-level (root) post in the window.
**Scope note:** the script does not classify intent — it emits *every* root post in the
look-back window, not only explicit merge/override/help asks. Some rows will be
unrelated chatter or FYIs (no PR link, `state = —`). Use the `PR(s)` and `State`
columns to find the actionable ones (a referenced PR that is `OPEN / BLOCKED`); rows
with no PR are usually discussion, not a request.

| Column | Meaning |
| --- | --- |
| PR(s) | GitHub PRs referenced in the post (from the message's own links) |
| Requester | Teams display name of the author |
| When | Post time (local) |
| Replies | Reply count + last-reply time (a cheap "is it resolved?" signal) |
| State | Live `gh` `state / mergeStateStatus` per PR (skip with `--no-gh`) |
| Teams | Canonical `l/message` permalink to the exact post (rendered as a `[message](…)` link) |
| Tagged you | `YES` when the post @-mentions the resolved name (`--mention`, else the logged-in Teams user) |

Also writes a full JSON report (`--json`) for downstream use.

## Why it reads IndexedDB (not the DOM)

The Teams web client caches every loaded channel message in IndexedDB:

- `Teams:conversation-manager:*` → `conversations` store: each channel record has
  `id` (the `19:...@thread.tacv2` **threadId**) and `threadProperties.{topic,groupId,tenantid}`.
  This is how the script maps a channel **display name → threadId/groupId/tenant**
  with zero hardcoding (portable across tenants/rotations).
- `Teams:replychain-manager:*` → `replychains` store: each record is a thread whose
  `messageMap` holds the messages. Per message: `id`, `parentMessageId`
  (`== id` ⇒ a root post; else a reply), `imDisplayName`, `originalArrivalTime`,
  `content` (HTML with the PR `<a href>`), and mention spans.

Reading this cache is far more reliable than driving the Teams UI, which
**drifts between turns, truncates channel names in the nav, blocks `innerHTML`
via Trusted Types, and hides message permalinks behind a hover menu.** The DOM
does **not** contain the channel threadId at all — only IndexedDB / app state does.

## Prerequisites

1. **Chrome (or Edge) running with remote debugging, signed into Teams.**
   The script can start one for you against a persistent profile:
   ```powershell
   python pull_gardener_requests.py --launch
   ```
   Manual equivalent:
   ```powershell
   Start-Process "C:\Program Files\Google\Chrome\Application\chrome.exe" `
     -ArgumentList '--remote-debugging-port=9222',
                   '--user-data-dir=C:\Users\<you>\.copilot\chrome-cdp-profile',
                   'https://teams.microsoft.com/v2/'
   ```
   The persistent `--user-data-dir` keeps you signed in across relaunches, so a
   crashed/closed browser recovers without a fresh AMD-Okta login.
2. `pip install pychrome`
3. `gh` authenticated (`gh auth status`) — only needed unless `--no-gh`.

## Usage

```powershell
cd scripts
# last 48h, both channels, live gh state, flag posts that @-tag you.
# --mention is optional: omit it and the script auto-detects the logged-in Teams user.
python pull_gardener_requests.py --json report.json --md report.md

# quick, no GitHub calls:
python pull_gardener_requests.py --hours 24 --no-gh

# force-load older/newer messages first (opens each channel + scrolls), then read:
python pull_gardener_requests.py --sync --hours 120

# start the browser first if CDP is down:
python pull_gardener_requests.py --launch
```

| Flag | Default | Purpose |
| --- | --- | --- |
| `--hours N` | 48 | look-back window for root posts |
| `--no-gh` | off | skip live PR state (much faster) |
| `--mention "Last, First"` | auto-detect | mark posts that @-mention this display name; if omitted, the logged-in Teams user (from the MSAL account cache) is used |
| `--sync` | off | before reading, open each channel via a trusted CDP click and scroll up to hydrate IndexedDB (best-effort; see below) |
| `--sync-scrolls N` | 6 | scroll-to-top passes per channel when `--sync` |
| `--launch` | off | launch Chrome with the persistent profile if CDP is down |
| `--team-name` | `AIG ROCm` | value put in the permalink `teamName=` param |
| `--json PATH` / `--md PATH` | — | also write the report to disk |

## Configuration

Edit the constants at the top of `scripts/pull_gardener_requests.py`:

- `CHANNEL_REPOS` — channel `topic` → GitHub `org/repo`. Add channels here.
- `CDP_URL` — debug endpoint (default `http://127.0.0.1:9222`).
- `CHROME_CANDIDATES`, `PROFILE_DIR` — used by `--launch`.

## How to run it as a gardener

1. Leave the CDP Chrome + Teams open all week (the live client keeps IndexedDB
   fresh as messages arrive). Re-run the script whenever you want a refresh.
2. Skim the table top-down: rows with `state = OPEN / BLOCKED` and a low reply
   count are the real work; `MERGED` / high-reply rows are usually already handled.
3. For any row you want to act on, hand the PR to the `monorepo_gardener_skill.md` `/gr`
   flow. This skill never merges, comments, or posts — it is read-only.

**Always keep the Teams message link per row.** Every row carries a `[message](…)`
permalink to the exact post in the `Teams` column. When you distill or re-present a
subset of these rows (e.g. an "actionable / still-open" table), **keep that Teams
message link in each row** so the reader can jump straight to the discussion — never
drop it when summarizing.

## Verification & trust

- Thread ids come straight from the running client's IndexedDB, so permalinks
  resolve to the exact post (`l/message/{threadId}/{messageId}?…` — the same
  string Teams' own "Copy link" emits). A raw browser hit lands on the standard
  "Open in Teams" launcher with all params intact; clicking while signed in
  scrolls to the message.
- Coverage is limited to what the client has cached. For a full back-scroll,
  open each channel and scroll up once so Teams loads older chains into
  IndexedDB, then re-run.

## Coverage: how the cache fills, and forcing older messages to load

The script is **passive**: it never navigates, clicks, or scrolls. It reads only
what the Teams web client has already written to IndexedDB. Two things follow:

- **Recent messages are always there.** The live client keeps the current and
  recent chains hot as they arrive, so for the normal gardener window (last
  24–48h) a passive read is complete as long as the browser has been open.
- **Deep back-scroll may be missing.** Messages older than what the client has
  loaded are simply not in IndexedDB yet. This is why a wide `--hours 120` can
  still miss a Friday post until the channel has been scrolled back — the window
  is one filter, cache coverage is a second, independent one.

**Forcing a load — the `--sync` flag (or do it by hand).** The reliable way to
hydrate older chains is to open each Gardening channel and scroll the message
pane up. `--sync` automates this: it delivers a **trusted** CDP click on each
channel and scrolls the pane to the top a few times, so the client fetches older
chains (and any brand-new posts) and writes them to IndexedDB before the read.
Equivalent manual path: click each channel in the CDP browser, scroll up once or
twice, then re-run without `--sync`.

`--sync` is **best-effort and readiness-gated** — it waits for the "setting
things up" splash to clear, hit-tests each channel item, and simply **skips with a
warning** (never a fake success) if a channel can't be clicked. Because it drives
the live UI it is inherently more fragile than the passive read, so it is opt-in;
the default run stays purely passive.

**How the trusted click works (and why synthetic clicks don't).** CDP's
`Input.dispatchMouseEvent` delivers a **real** click (`isTrusted=true`) that Teams
honours, unlike a JS `element.click()` (`isTrusted=false`) that Fluent UI ignores.
Two things make blind clicks miss, both handled by `--sync`:

- **Readiness.** A backgrounded Teams tab often shows a full-viewport
  "We're setting things up for you…" splash (`[class*="fade-out-animation"]`,
  `z-index:4`). A click during that hits the splash. `--sync` waits it out.
- **Hit-testing.** `--sync` confirms `document.elementFromPoint(cx,cy)` is inside
  the target before dispatching, so a dialog/toast/splash can't cause a silent miss.
- **`document.title` is not a reliable signal** — it shows a stale app area plus an
  unread count (e.g. "(9) Calendar"), not the open channel; verify from the DOM.

## Gotchas (learned the hard way)

1. **Trusted Types**: assigning `element.innerHTML` throws in Teams. The extractor
   uses `DOMParser().parseFromString` to strip HTML instead.
2. **Stale reads look live**: if Chrome/CDP dies, a naive helper that swallows
   stderr will silently re-read an old dump. This script fails loudly when the
   CDP endpoint is down (or launches a fresh browser with `--launch`).
3. **Redirected output is not the issue here** — the script talks CDP directly and
   parses `returnByValue`, avoiding the PowerShell UTF-16 redirect trap that bites
   `gh ... > file`.
4. **`mergeStateStatus: UNKNOWN` on a MERGED PR is normal** — GitHub stops
   computing mergeability once a PR is closed/merged.

## Files

- `scripts/pull_gardener_requests.py` — CDP driver + `gh` enrichment + formatting.
- `scripts/pull_messages.js` — async IndexedDB extractor injected into the Teams tab.
