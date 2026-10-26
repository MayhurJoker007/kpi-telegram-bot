"""Builds demo.db: three weeks of field audits and orders, with a bad day on purpose so the alerts fire.

    python demo/make_demo_db.py
"""
import random
import sqlite3
from datetime import date, timedelta

rng = random.Random(3)
db = sqlite3.connect('demo.db')
db.executescript('''
DROP TABLE IF EXISTS audit; DROP TABLE IF EXISTS orders;
CREATE TABLE audit (id INTEGER PRIMARY KEY, visited_on TEXT, score REAL, passed_qc INTEGER);
CREATE TABLE orders (id INTEGER PRIMARY KEY, placed_on TEXT, total REAL, status TEXT);
''')
end = date.today() - timedelta(days=1)
for i in range(21):
    day = end - timedelta(days=20 - i)
    weekend = day.weekday() >= 5
    bad_day = day == end              # yesterday went badly: fewer audits, lower QC pass rate
    for _ in range(rng.randint(15, 25) if weekend else rng.randint(55, 75) if not bad_day else 31):
        score = rng.gauss(78 if not bad_day else 64, 9)
        db.execute('INSERT INTO audit (visited_on, score, passed_qc) VALUES (?, ?, ?)',
                   (day.isoformat(), round(score, 1), int(rng.random() < (0.93 if not bad_day else 0.74))))
    for _ in range(rng.randint(40, 70)):
        db.execute('INSERT INTO orders (placed_on, total, status) VALUES (?, ?, ?)',
                   (day.isoformat(), round(rng.uniform(300, 6000), 2), rng.choice(['delivered'] * 9 + ['cancelled'])))
db.commit()
print('demo.db ready, up to', end)
