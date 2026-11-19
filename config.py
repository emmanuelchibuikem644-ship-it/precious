"""Central configuration for the Smart Attendance System.

All tunable values live here so that behaviour can be adjusted without
touching the application logic.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("SAFR_DATA_DIR", BASE_DIR / "data"))

APP_TITLE = "Smart Attendance System"
INSTITUTION = "Ignatius Ajuru University of Education"
DEPARTMENT = "Department of Computer Science"

DB_PATH = DATA_DIR / "attendance_system.db"
TEMPLATE_DIR = DATA_DIR / "templates"
KEY_PATH = DATA_DIR / "keys" / "template.key"
BACKUP_DIR = DATA_DIR / "backups"
EXPORT_DIR = DATA_DIR / "exports"

# ---- Recognition parameters -------------------------------------------
TOLERANCE = 0.60           # maximum Euclidean distance for a positive match
SAMPLES_REQUIRED = 5       # face samples captured per student at enrolment
CONFIRM_FRAMES = 3         # consecutive processed frames before attendance is written
DETECT_SCALE = 0.5         # frames are shrunk by this factor before HOG detection
PROCESS_EVERY_N = 2        # recognition runs on every Nth camera frame
MIN_FACE_PIXELS = 80       # smallest acceptable face height (px) at enrolment
UNKNOWN_LOG_INTERVAL = 10  # seconds between "unrecognised face" audit entries

# ---- Security parameters ----------------------------------------------
SESSION_TIMEOUT_MIN = 30
BCRYPT_ROUNDS = 12
MIN_PASSWORD_LENGTH = 8
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 10

# ---- Reporting ----------------------------------------------------------
ATTENDANCE_THRESHOLD = 75.0   # percent; below this a student is flagged as a defaulter
BACKUP_KEEP = 14              # number of daily backups retained
