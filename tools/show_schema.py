"""Print the schema that the application created (equivalent to:  sqlite3 attendance_system.db .schema)."""
import sqlite3
import sys

path = sys.argv[1]
con = sqlite3.connect(path)
for name, sql in con.execute("SELECT name, sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type DESC, rowid"):
    print(sql.strip() + ";")
    print()
