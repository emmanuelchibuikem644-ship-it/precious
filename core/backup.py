"""Daily database backups with simple retention."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import config
from core.database import Database


def list_backups(directory: str | Path | None = None) -> list[Path]:
    d = Path(directory or config.BACKUP_DIR)
    return sorted(d.glob("attendance_*.db"), reverse=True) if d.exists() else []


def prune(directory: str | Path | None = None, keep: int | None = None) -> int:
    keep = config.BACKUP_KEEP if keep is None else keep
    old = list_backups(directory)[keep:]
    for p in old:
        p.unlink(missing_ok=True)
    return len(old)


def ensure_daily_backup(db: Database, directory: str | Path | None = None, actor: str = "system") -> Path | None:
    """Create today's backup if it does not exist yet (called every time the application starts)."""
    directory = Path(directory or config.BACKUP_DIR)
    stamp = datetime.now().strftime("%Y%m%d")
    if any(p.name.startswith(f"attendance_{stamp}") for p in list_backups(directory)):
        return None
    dest = db.backup_to(directory)
    prune(directory)
    db.log(actor, "BACKUP", f"Automatic daily backup -> {dest.name}")
    return dest
