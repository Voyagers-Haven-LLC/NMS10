"""CLI wrapper around app.db.backup_now() + prune_old_backups().

Usage (from backend/ with venv activated):
    python -m scripts.backup_db
    python -m scripts.backup_db --reason="pre-deploy"
    python -m scripts.backup_db --no-prune

Output:
    Backup written to: <path> (NN.N KB)
    Total backups retained: <count> (oldest: <date>)
    Pruned <N> backups older than 30 days
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure we can import the app module when invoked as `python -m scripts.backup_db`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Snapshot nms10.db to data/backups/")
    parser.add_argument(
        "--reason",
        default="manual",
        help="Logged with the backup line; useful for grepping later.",
    )
    parser.add_argument(
        "--no-prune",
        action="store_true",
        help="Skip the 30-day retention sweep (keep every existing backup).",
    )
    parser.add_argument(
        "--retain-days",
        type=int,
        default=db.BACKUP_RETAIN_DAYS,
        help=f"How many days of backups to keep (default: {db.BACKUP_RETAIN_DAYS}).",
    )
    args = parser.parse_args()

    try:
        dest = db.backup_now(reason=args.reason)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: backup failed: {exc}", file=sys.stderr)
        return 1

    size_kb = dest.stat().st_size / 1024
    print(f"Backup written to: {dest} ({size_kb:.1f} KB)")

    pruned = 0
    if not args.no_prune:
        pruned = db.prune_old_backups(retain_days=args.retain_days)

    backups = db.list_backups()
    if backups:
        oldest = backups[0]
        try:
            oldest_dt = datetime.fromtimestamp(oldest.stat().st_mtime, tz=timezone.utc)
            oldest_str = oldest_dt.strftime("%Y-%m-%d %H:%M UTC")
        except OSError:
            oldest_str = "unknown"
        print(f"Total backups retained: {len(backups)} (oldest: {oldest_str})")
    else:
        print("Total backups retained: 0")

    if pruned:
        print(f"Pruned {pruned} backup(s) older than {args.retain_days} days")
    return 0


if __name__ == "__main__":
    sys.exit(main())
