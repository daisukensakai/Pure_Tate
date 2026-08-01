# Grok worker dispatch logs

Durable logs of optional Grok 4.5 worker dispatches from Pure Tate agent runs. Temp task workspaces are deleted after each run; this folder is not.

- `events.jsonl` — global append-only event stream
- `sessions/<SESS-id>/session.json` — parent task metadata
- `sessions/<SESS-id>/events.jsonl` — per-parent-session events
- `sessions/<SESS-id>/workers/` — durable worker stdout/stderr
- `latest.txt` — most recent session id
