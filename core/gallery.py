"""Loads every enrolled student's encrypted face template into the recognition engine."""
from __future__ import annotations

from cryptography.exceptions import InvalidTag


def load_gallery(db, vault, engine) -> int:
    """Decrypt all templates and hand them to the engine. Tampered or missing files are skipped
    (and the tampering is written to the audit log). Returns the number of identities loaded."""
    entries = []
    for s in db.list_students():
        if not s["face_template_path"]:
            continue
        try:
            array = vault.load(s["face_template_path"])
        except InvalidTag:
            db.log("system", "TEMPLATE_TAMPERED", f"Template for {s['matric_number']} failed authentication")
            continue
        except FileNotFoundError:
            db.log("system", "TEMPLATE_MISSING", f"Template file for {s['matric_number']} not found")
            continue
        entries.append((s["student_id"], s["matric_number"], f"{s['first_name']} {s['last_name']}", array))
    engine.load_gallery(entries)
    return len(entries)
