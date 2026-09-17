# Local Hot-Reload (Backend Python Services)

All four Python backend services support **hot-reload** in local development:
edit a source file, save, and the running container picks up the change with no
rebuild and no manual restart.

| Service | Kind | Reloader | Watched paths (in container) |
|---------|------|----------|------------------------------|
| `api_gateway` | FastAPI / uvicorn | `uvicorn --reload` | `/app/app`, `/app/livestockguard_common` |
| `mqtt_writer` | plain worker | `watchfiles` CLI | `/app/mqtt_writer.py`, `/app/livestockguard_common` |
| `alert_engine` | plain worker | `watchfiles` CLI | `/app/app`, `/app/livestockguard_common` |
| `analytics_engine` | plain worker | `watchfiles` CLI | `/app/app` |

> `analytics_engine` vendors only its own `app/` (its Dockerfile does not copy
> `livestockguard_common`), so only `app/` is mounted and watched.

## How it works

Hot-reload is a **development-only** convenience wired entirely in
`cloud/docker-compose.yml`. The Dockerfiles are unchanged in behaviour for
production — they still `COPY` the source into the image and define the normal
`CMD`. In production (or anywhere the compose file below is not used) the mounts
and reload commands are absent, so images run exactly as built.

For each service, compose adds three things:

1. **A source bind-mount** over the baked-in copy, e.g.
   ```yaml
   volumes:
     - ./services/api_gateway/app:/app/app
     - ./shared/livestockguard_common:/app/livestockguard_common
   ```
   Your local files now *are* the files the container runs.

2. **A reload-aware `command`** that overrides the image `CMD`:
   - `api_gateway` (uvicorn has this built in):
     ```yaml
     command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000",
                "--reload", "--reload-dir", "/app/app",
                "--reload-dir", "/app/livestockguard_common"]
     ```
   - The plain workers are not web servers, so they are wrapped with the
     `watchfiles` CLI, which reruns the process when a watched path changes:
     ```yaml
     command: ["watchfiles", "python -m app.main", "/app/app", "/app/livestockguard_common"]
     ```

3. **`WATCHFILES_FORCE_POLLING: "true"`** — the critical bit on macOS.
   Docker Desktop / Colima run containers inside a Linux VM, and macOS bind
   mounts do **not** forward filesystem (inotify) events into that VM. Native
   file watching therefore silently misses your edits. Polling works reliably
   across the VM boundary at the cost of a little CPU. Both `uvicorn --reload`
   and the `watchfiles` CLI honour this variable (uvicorn's reloader is
   `watchfiles` under the hood).

`watchfiles` is declared in each worker's `requirements.txt`; `uvicorn[standard]`
already bundles it for `api_gateway`.

## First-time activation

Because two services (`alert_engine`, `analytics_engine`) and `mqtt_writer`
gained a new dependency (`watchfiles`), their images must be rebuilt **once**.
After that, just save files.

```bash
# From the repo root — rebuild the workers once to install watchfiles
docker compose -f cloud/docker-compose.yml build \
  mqtt_writer alert_engine analytics_engine

# (Re)create all backend containers with the reload command + mounts
docker compose -f cloud/docker-compose.yml up -d \
  api_gateway mqtt_writer alert_engine analytics_engine
```

`api_gateway` did not gain a dependency, so a plain
`up -d api_gateway` (no rebuild) is enough for it.

## Verifying it works

Edit any watched file and watch the logs — you should see a reload line:

```bash
# api_gateway (uvicorn)
docker compose -f cloud/docker-compose.yml logs -f api_gateway
#   WARNING:  WatchFiles detected changes in 'app/main.py'. Reloading...

# a worker (watchfiles CLI)
docker compose -f cloud/docker-compose.yml logs -f mqtt_writer
#   [hh:mm:ss] N changes detected
```

A quick end-to-end check for `api_gateway`:

```bash
curl -s http://localhost:8000/health
# edit app/main.py, save, wait ~2-3s, curl again — the response reflects the edit
```

## Notes & gotchas

- **Polling overhead** is small and dev-only. It applies solely to these
  containers via the compose file; production deployments have neither the
  mounts nor the `--reload` / `watchfiles` command.
- **Syntax errors** crash the process on reload. `watchfiles` keeps watching and
  will restart cleanly once you fix and save again; `uvicorn --reload` behaves
  the same. Check the service logs if a container looks stuck.
- **New dependencies still need a rebuild.** Hot-reload only re-runs Python
  source. If you add a package to a `requirements.txt`, rebuild that service's
  image (`docker compose build <service>`).
- **`herding_orchestrator`** is intentionally left without hot-reload for now
  (it maintains MQTT/robot control-loop state that is cleaner to restart
  explicitly). Add the same pattern if you want it — mount
  `./services/herding_orchestrator/app`, set `WATCHFILES_FORCE_POLLING`, and use
  the `watchfiles` command wrapper.
- **Shared code** (`livestockguard_common`) is mounted into every service that
  uses it, so a change there hot-reloads all of them at once.
