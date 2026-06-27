# Cosolvent on Windows — Build Gotchas & Fixes

Practical companion to [`TEST-COSOLVENT_AND COMMONCONTEXT.md`](../TEST-COSOLVENT_AND%20COMMONCONTEXT.md)
for anyone building/running the generated marketplace on a **Windows** machine.
Verified end-to-end on 2026-06-26 (Windows 11 + WSL2 Ubuntu-24.04 + Docker Desktop):
live stack at `http://localhost:18000/docs`, 98 endpoints, 59 knowledge chunks
loaded for vertical `machinery_trade`.

> macOS/Linux users can ignore most of this — these are Windows-specific traps caused
> by WSL2, Docker Desktop, and git's symlink handling.

---

## 0. Golden rule: run everything inside WSL2, not PowerShell/Git Bash

`make` and the Docker daemon only answer **inside the WSL2 distro** (Ubuntu-24.04).
The repo is reached from WSL via `/mnt/c/...`:

```bash
cd /mnt/c/Users/<you>/GitHub/Cosolvent
make live-from-docs
```

Running `make` from native PowerShell/CMD or Git Bash will fail (`make: command not found`,
or Docker pipe errors).

---

## 1. Python venvs must be **Linux** venvs

The Makefiles call `.venv/bin/python` (POSIX layout). A venv created on Windows has
`.venv/Scripts/python.exe` instead and will not work under WSL. Build fresh Linux venvs
**from inside WSL** in both repos:

```bash
cd /mnt/c/.../GitHub/CommonContext && make install
cd /mnt/c/.../GitHub/Cosolvent     && make install   # creates backend/.venv
```

- If a Windows `.venv` already exists, deleting it from WSL can fail with `Input/output error`
  (a running `python.exe` may hold `Scripts/python.exe`). You don't need to delete it —
  `python3 -m venv .venv` overlays a Linux `bin/` alongside the Windows `Scripts/`.
- CommonContext's deps pull **torch + CUDA wheels (~2.5 GB)** via `marker-pdf`. This is
  intentional and portable: torch uses CUDA where an NVIDIA GPU exists and falls back to
  CPU otherwise (e.g. AMD Radeon machines). No action needed.

---

## 2. `OPENROUTER_API_KEY` is required

Stage 1 (schema synthesis + embeddings) calls an LLM. Put the key in **`CommonContext/.env`**
(and `Cosolvent/.env`); both are gitignored. Without it, `make live-from-docs` aborts in stage 1.

```
OPENROUTER_API_KEY=sk-or-v1-...
```

---

## 3. Two git symlinks get checked out as **text files** (breaks `make compile`)

`backend/openapi` and `backend/generated` are committed as **symlinks** (git mode `120000`,
pointing at `../openapi` and `../generated`). Windows clones with `core.symlinks=false`, so
they land as 10–12 byte **text files** containing the link target. `make compile` then dies:

```
FileExistsError: [Errno 17] File exists: '.../backend/openapi'
  at  (root / openapi_rel).parent.mkdir(parents=True, exist_ok=True)
```

**Fix — recreate them as real symlinks (in WSL), with their target dirs:**

```bash
cd /mnt/c/.../GitHub/Cosolvent
mkdir -p openapi generated
rm -f backend/openapi backend/generated
ln -s ../openapi    backend/openapi
ln -s ../generated  backend/generated
```

### The dual-OS catch (important)
There is **no working-tree state that is clean from both Windows-git and WSL-git at once**:

| State of `backend/openapi`,`backend/generated` | `make compile` | Windows git | WSL git |
|---|---|---|---|
| Text-file placeholder (fresh Windows clone) | ❌ fails | ✅ clean | ⚠️ typechange |
| Real WSL symlink (the fix above) | ✅ works | ❌ shows "deleted" / `Function not implemented` | ✅ clean |

So: **apply the symlink fix to build, then restore the placeholders to keep Windows git clean:**

```bash
printf '../openapi'    > backend/openapi
printf '../generated'  > backend/generated
```

(The running stack does not need the symlinks after `compile` — the artifacts are already
generated into `openapi/` and `generated/`.)

A permanent alternative: enable Windows Developer Mode + `git config core.symlinks true`
and re-checkout, so Windows materializes real NTFS symlinks. Then both gits stay clean and
builds work — at the cost of a one-time global setup.

---

## 4. Docker Desktop's WSL-integration socket can disappear

Symptom — `make reset`/`up` fail with:

```
failed to connect to the docker API at unix:///var/run/docker.sock ... no such file or directory
```

`/var/run/docker.sock` gets injected into the distro by Docker Desktop's WSL integration,
but it can **drop after the distro idle-restarts**, and:
- `wsl --shutdown` does **not** reliably re-inject it.
- The integration proxy (`/mnt/wsl/docker-desktop/docker-desktop-user-distro proxy`) needs
  **root** to recreate the socket — you can't start it by hand without sudo.

**Fix:** Docker Desktop → **Settings → Resources → WSL Integration** → enable **Ubuntu-24.04**
→ **Apply & Restart**. The socket returns as:

```
srw-rw---- 1 root docker  /var/run/docker.sock
```

(Your WSL user is in the `docker` group, so this is accessible without sudo.) Verify:

```bash
docker info --format 'Server={{.ServerVersion}}'
```

---

## 5. Don't be alarmed by these (they're correct, not failures)

- `POST /api/ai/knowledge` → **`401 Not authenticated`**: public signup is disabled by default
  (`ALLOW_PUBLIC_SIGNUP` empty). The endpoint requires a session. To test it, seed a user or
  set `ALLOW_PUBLIC_SIGNUP=1` in `Cosolvent/.env` and rebuild. The knowledge data is loaded
  regardless (verify directly: `docker exec cosolvent-postgres-1 psql -U postgres -d cosolvent
  -c "select count(*) from reference_library;"`).
- `backend/alembic/versions/auto_marketplace_*.py` appearing untracked: it's a **generated**
  migration from `make compile`; regenerates each build.

---

## Quick resume (when stages 1–2 already ran)

`make live-from-docs` re-runs the full pipeline (and re-spends OpenRouter credits on stage 1).
If schema + `marketplace.yaml` already exist and only the stack needs (re)building:

```bash
make compile && make reset && make up && make wait-api && make load-knowledge
```
