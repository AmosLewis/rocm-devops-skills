# tgr — Teams Gardener Requests pull

> For use with **Cursor** custom commands (`/tgr`) or as a prompt for **Claude CLI**.

Context: Read `gardener/teams_gardener_requests_skill.md` first and follow it.

Use this to refresh the list of open merge/override/force-merge/help requests from the
**Gardening - rocm-libraries** and **Gardening - rocm-systems** Teams channels, cross-referenced to
live GitHub PR state, with a Teams message permalink per row.

## Instructions

1. Confirm the Chrome CDP endpoint is up (a browser started with `--remote-debugging-port` and signed
   into Teams). If it is down, start it with `--launch` — do not silently re-read a stale dump.
2. Run the pull from `gardener/scripts/`:

   ```powershell
   cd gardener/scripts
   python pull_gardener_requests.py --sync --hours 48 --json report.json --md report.md
   ```

   - `--sync` hydrates IndexedDB with a trusted CDP click + scroll so recent/older chains are loaded
     before the read. Drop it for a faster passive read once the channels are already open.
   - Omit `--mention` and the script auto-detects the logged-in Teams user for @-tag flagging; pass
     `--mention "Last, First"` to flag someone else.
3. Present the actionable subset (`state = OPEN / BLOCKED` or `UNSTABLE`, low reply count) top-down.
   **Keep the Teams `[message](…)` permalink in every row** — never drop it when summarizing.
4. Flag any row where `Tagged you = YES` first — that is a direct ask.
5. This skill is **read-only**: it never merges, comments, or posts. Hand any row you want to act on to
   the `monorepo-gardener` `/gr` (per-request triage) flow.
6. Do not commit `report.json` / `report.md` — they contain tenant/user data and are gitignored.

## Example usage

```
/tgr
```

Or a wider window with a specific person to flag:

```
/tgr --hours 120 --mention "Last, First"
```
