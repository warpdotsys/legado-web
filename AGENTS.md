# AGENTS.md — legado-web (Docker port of legado)

Repository-specific memory for the OpenHands agent.

## What this project is
A Python re-implementation of the legado Android book reader's WebService layer
(NanoHTTPD :1122) + WebSocketServer (:1123), with a native vanilla-JS web UI.
API-compatible with legado: every response is `{isSuccess, errorMsg, data}`.

- `backend/server.py` — HTTP :1122 + WebSocket :1123 entrypoint. Ports via
  env `LEGADO_WEB_PORT` (WS = port+1). DB path via `LEGADO_DB` (default `/data/legado.db`).
- `backend/api.py` — Controllers (Book/BookSource/RssSource/ReplaceRule) + `ReturnData`.
- `backend/database.py` — SQLite DAO, schema aligned with legado entities.
- `frontend/` — SPA, no build step. `js/api.js` paths must match `server.py` route table.

## Build / run
```bash
docker compose up -d --build   # open http://localhost:1122
python3 backend/server.py      # local, no docker
```

## Deploy target: de.medwarp.cn (root via SSH key)
- **SSH**: `ssh -i ~/.ssh/de_medwarp_key root@de.medwarp.cn` (key perms MUST be 600).
  `openssh-client` + `rsync` are NOT in the sandbox by default — `apt-get install openssh-client rsync`.
  Remote has NO rsync either; deploy with `tar | ssh ... 'tar x'`.
- **Deploy path**: `/opt/legado-web` (do NOT touch `/opt/legado` — that's a separate
  gradle/APK-based attempt using ports 4080-4082).
- **Docker** is preinstalled on the host (29.5.x + Compose v5).
- **Build DNS gotcha**: the default docker build network CANNOT resolve pypi.org on this host
  (daemon.json sets dns 1.1.1.1 but the build net can't reach it). MUST build with
  `network: host` in compose's `build:` block, else `pip install` fails with
  "Temporary failure in name resolution". This is already in the committed docker-compose.yml.
- Ports 1122/1123 are free and publicly reachable: `http://de.medwarp.cn:1122` (HTTP 200),
  `ws://de.medwarp.cn:1123` (101 Switching Protocols). Host firewall (iptables INPUT) is ACCEPT.
- The sandbox itself CANNOT make outbound connections to de.medwarp.cn (all ports time out,
  incl. known-working 4396/8050). Verify reachability from the server itself:
  `ssh root@de.medwarp.cn 'curl -s -o /dev/null -w "%{http_code}" http://de.medwarp.cn:1122/'`.

## GitHub
- Repo: `warpdotsys/legado-web` (org already has `legado` = original source — don't reuse the name).
  Created via `POST /orgs/warpdotsys/repos`. Push with token in URL, then reset remote to clean URL.

## legado API path conventions (gotcha — don't second-guess)
These are the ACTUAL legado paths (matching HttpServer.kt), not intuitive ones:
- `/saveBook` (capital B), `/deleteBook` — NOT /savebook, /deletebook
- `/getReadConfig`, `/saveReadConfig` — NOT /getWebReadConfig
- `/cover?url=`, `/image?url=` — NOT /getCover, /getImg
- `/deleteBookSources`, `/deleteRssSources` (PLURAL, batch) vs `/saveBookSource` (singular)
- `/deleteReplaceRule` (singular)
- Empty bookshelf/RSS legitimately returns `isSuccess:false` with errorMsg — that's real legado behavior, not a bug.

## Verified working (as of deploy)
Container `legado-web` healthy, restart unless-stopped, data in `legado-web_legado-data` volume.
Fresh DB auto-seeds one demo book source "笔趣阁(示例源)".
