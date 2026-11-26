import sqlite3

conn = sqlite3.connect('data/cerberus_x.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print('Tables in DB:', tables)
counts = {}
for t in tables:
    if not t.startswith('sqlite_'):
        counts[t] = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
print('Counts:', counts)
