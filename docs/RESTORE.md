# Restoring the NMS10 database from a backup

The site stores everything in one SQLite file: `data/nms10.db`. If it's
corrupted, deleted, or you want to roll back to a known-good state, every
backup is a complete, ready-to-use copy of that file.

## Where backups live

```
data/backups/nms10-YYYYMMDD-HHMMSS.db
```

- **Daily** snapshots fire at 03:00 local time via APScheduler.
- **First-boot** snapshot fires once if no backups exist yet.
- **Preflight** snapshots fire automatically before any admin DELETE
  (bases, communities, meetups, socials, gallery images). Each is logged
  with the reason in `data/logs/backup.log`.
- **30-day rotation**: backups older than 30 days get pruned at the end of
  each backup run.

## Quick: how to restore (3 steps)

1. **Stop the backend** so nothing's writing to the live DB.
   ```cmd
   :: Find and stop the uvicorn process
   taskkill /F /IM python.exe /FI "WINDOWTITLE eq *uvicorn*"
   ```
   Or just Ctrl+C in the terminal running uvicorn.

2. **Copy the backup over `nms10.db`**.
   ```cmd
   :: Replace YYYYMMDD-HHMMSS with the snapshot you want
   copy /Y C:\Users\parke\nms10\data\backups\nms10-YYYYMMDD-HHMMSS.db ^
            C:\Users\parke\nms10\data\nms10.db
   ```

3. **Start the backend**.
   ```cmd
   cd C:\Users\parke\nms10\backend
   .venv\Scripts\python.exe -m uvicorn app.main:app --reload
   ```

That's it. The schema is already in the backup file (it's a complete copy,
not a delta), and `init_db()` only runs `CREATE TABLE IF NOT EXISTS` so it
won't disturb anything.

## How to confirm the restore worked

Three quick checks:

```cmd
:: 1. Backend health
curl http://localhost:8000/api/health

:: 2. Spot-check counts match what you expect from that snapshot
curl http://localhost:8000/api/bases | python -c "import sys,json; print(len(json.load(sys.stdin)),'bases')"
curl http://localhost:8000/api/communities | python -c "import sys,json; print(len(json.load(sys.stdin)),'communities')"
curl http://localhost:8000/api/meetups | python -c "import sys,json; print(len(json.load(sys.stdin)),'meetups')"

:: 3. Log into the admin panel — http://localhost:5173/admin
:: A successful login confirms the admin_users table is intact.
```

If the counts match the snapshot's vintage, you're done.

## How to find the most recent backup

```cmd
:: Show all backups, newest first
dir C:\Users\parke\nms10\data\backups\nms10-*.db /O-D

:: Or just print the newest filename
powershell "Get-ChildItem C:\Users\parke\nms10\data\backups\nms10-*.db | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty Name"
```

The filename format is `nms10-YYYYMMDD-HHMMSS.db`, **UTC time**, so it's
trivially sortable.

## How to manually trigger a backup

Useful before risky operations (manual schema changes, mass data import,
upgrading dependencies that touch SQLAlchemy):

```cmd
cd C:\Users\parke\nms10\backend
.venv\Scripts\python.exe -m scripts.backup_db
```

Output:
```
Backup written to: C:\Users\parke\nms10\data\backups\nms10-20260506-203000.db (100.0 KB)
Total backups retained: 23 (oldest: 2026-04-08 03:00 UTC)
Pruned 1 backup(s) older than 30 days
```

Optional flags:
- `--reason="pre-deploy"` — annotates the log line so you can grep for it
  later in `data/logs/backup.log`.
- `--no-prune` — skip the 30-day cleanup; useful when you want to preserve
  every backup during a recovery exercise.
- `--retain-days=N` — override the retention window for this one run.

## What to do when something feels wrong

- **"Lost data" but unsure when**: open `data/logs/backup.log` and
  `git log` side by side. Backup log timestamps tell you when each
  snapshot was made; `git log` tells you what code was running. Pick a
  snapshot from before the loss happened.
- **Restore restored too far back**: just restore again from a more recent
  snapshot. The DB file itself is the source of truth — copying over it is
  cheap and reversible.
- **No backups at all**: check Windows File History
  (Properties → Previous Versions on the `data` folder) and OneDrive's
  recycle bin. If neither has a snapshot, the data is unrecoverable.

## How the backup itself works

Uses SQLite's [online backup API](https://www.sqlite.org/backup.html),
not a file copy. Important because:

- The backup is **atomic**: it can run while the backend is reading and
  writing to the DB without producing a corrupted snapshot.
- The result is a **complete, page-by-page copy** of the live DB at the
  moment the backup started — including indexes and the schema itself.
- It's safe to use the backup file directly: copy it over `nms10.db`,
  start the backend, done. No "replay" or schema migration needed.

The implementation is in [`backend/app/db.py:backup_now()`](../backend/app/db.py).

## The "I really do want to wipe the DB" path

If you're absolutely sure (e.g. you've taken a backup, or you're seeding
a fresh environment), the wipe tripwire only opens when this env var
is set:

```
NMS10_ALLOW_DB_WIPE=yes
```

This is intentional friction — without it, any code path that tries to
delete the live DB will raise `RuntimeError`. The tripwire lives in
[`backend/app/db.py:refuse_to_wipe_unless_explicit()`](../backend/app/db.py).

There are currently **no internal code paths** that call this — it's a
defense-in-depth check for future contributors who might add a "reset"
helper. If you ever see the tripwire fire, **read the message** before
flipping the env var. The message names what's about to be wiped.
