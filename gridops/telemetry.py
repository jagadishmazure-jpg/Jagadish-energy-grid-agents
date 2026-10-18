"""Synthetic grid telemetry on SQLite.

Fictional utility "Lakeshore Power & Light". All data is generated with a
fixed seed (42), so every run produces the same database. Deterministic
anchors are planted for tests and demos:

- OUT-SEV-01: feeder F-101 fault, 12,400 customers out, Lakeshore General
  Hospital on the feeder -> severity critical, escalation T1.
- OUT-STORM-02: feeder F-207, storm damage, 3,100 customers, ETR 6h -> T2.
- CREW-A-07: line crew, skills {overhead, switching}, on shift, depot 4 km
  from OUT-SEV-01 -> the dispatch optimizer's top pick.
- F-114: load reading 38% above its 7-day baseline -> load anomaly.
- STORM-09: storm cell tracked toward the north service area -> T2 watch.
"""

from __future__ import annotations

import random
import sqlite3
from pathlib import Path

SEED = 42

SUBSTATIONS = [
    ("SUB-NORTH", "North service area", 4),
    ("SUB-SOUTH", "South service area", 3),
    ("SUB-EAST", "East service area", 3),
]

FEEDERS = [
    # (feeder_id, substation, customers, critical_facilities, baseline_mw)
    ("F-101", "SUB-NORTH", 12400, "Lakeshore General Hospital", 42.0),
    ("F-102", "SUB-NORTH", 8600, "North Water Treatment Plant", 31.5),
    ("F-103", "SUB-NORTH", 5200, "", 18.2),
    ("F-104", "SUB-NORTH", 4900, "Ridgeview Senior Care", 16.8),
    ("F-205", "SUB-SOUTH", 9100, "", 29.4),
    ("F-206", "SUB-SOUTH", 7300, "Southside Fire Station 3", 24.1),
    ("F-207", "SUB-SOUTH", 3100, "", 11.6),
    ("F-308", "SUB-EAST", 6800, "Eastside Data Hub", 27.9),
    ("F-309", "SUB-EAST", 5400, "", 19.3),
    ("F-310", "SUB-EAST", 4700, "Harborview School", 15.2),
    ("F-114", "SUB-NORTH", 6100, "", 22.4),  # load-anomaly anchor feeder
]

CAUSES = ["equipment-failure", "storm-damage", "vehicle-impact", "vegetation", "unknown"]

CREWS = [
    # (crew_id, skills, depot_substation, depot_km_from_F101, shift)
    ("CREW-A-07", "overhead,switching", "SUB-NORTH", 4.0, "day"),
    ("CREW-A-11", "overhead", "SUB-NORTH", 9.5, "day"),
    ("CREW-B-03", "underground,switching", "SUB-SOUTH", 22.0, "day"),
    ("CREW-B-09", "overhead,switching", "SUB-SOUTH", 26.5, "night"),
    ("CREW-C-02", "vegetation,overhead", "SUB-EAST", 31.0, "day"),
    ("CREW-C-05", "switching", "SUB-EAST", 28.0, "night"),
]


def build_db(path: str | Path) -> Path:
    """Build the synthetic grid database deterministically. Returns the path."""
    path = Path(path)
    if path.exists():
        path.unlink()
    rng = random.Random(SEED)
    con = sqlite3.connect(path)
    cur = con.cursor()

    cur.execute("""CREATE TABLE substations (
        substation_id TEXT PRIMARY KEY, area TEXT, feeder_count INTEGER)""")
    cur.execute("""CREATE TABLE feeders (
        feeder_id TEXT PRIMARY KEY, substation_id TEXT, customers INTEGER,
        critical_facilities TEXT, baseline_mw REAL)""")
    cur.execute("""CREATE TABLE outages (
        outage_id TEXT PRIMARY KEY, feeder_id TEXT, cause TEXT,
        customers_out INTEGER, started_utc TEXT, etr_hours REAL,
        status TEXT, critical_facility_affected INTEGER)""")
    cur.execute("""CREATE TABLE crews (
        crew_id TEXT PRIMARY KEY, skills TEXT, depot_substation TEXT,
        depot_km_from_f101 REAL, shift TEXT, status TEXT)""")
    cur.execute("""CREATE TABLE load_readings (
        reading_id INTEGER PRIMARY KEY, feeder_id TEXT, ts_utc TEXT,
        mw REAL, baseline_mw REAL)""")

    cur.executemany("INSERT INTO substations VALUES (?,?,?)", SUBSTATIONS)
    cur.executemany("INSERT INTO feeders VALUES (?,?,?,?,?)", FEEDERS)

    # Deterministic anchors first.
    anchors = [
        ("OUT-SEV-01", "F-101", "equipment-failure", 12400,
         "2026-10-18T04:12:00Z", 8.0, "active", 1),
        ("OUT-STORM-02", "F-207", "storm-damage", 3100,
         "2026-10-18T02:40:00Z", 6.0, "active", 0),
        ("OUT-VEG-03", "F-309", "vegetation", 5400,
         "2026-10-17T22:05:00Z", 4.0, "restoring", 0),
    ]
    cur.executemany("INSERT INTO outages VALUES (?,?,?,?,?,?,?,?)", anchors)

    # A few extra background outages (deterministic via seed).
    extra = []
    for i in range(4):
        feeder = FEEDERS[rng.randrange(len(FEEDERS))][0]
        extra.append((
            f"OUT-BG-{i+1:02d}", feeder, rng.choice(CAUSES),
            rng.randrange(200, 2500),
            f"2026-10-{rng.choice(['16','17'])}T{rng.randrange(24):02d}:00:00Z",
            round(rng.uniform(2.0, 10.0), 1),
            rng.choice(["active", "active", "restoring"]),
            0,
        ))
    cur.executemany("INSERT INTO outages VALUES (?,?,?,?,?,?,?,?)", extra)

    crews = [(c[0], c[1], c[2], c[3], c[4], "available") for c in CREWS]
    # CREW-B-09 is committed to another job -> not dispatchable.
    crews = [c if c[0] != "CREW-B-09" else (c[0], c[1], c[2], c[3], c[4], "committed")
             for c in crews]
    cur.executemany("INSERT INTO crews VALUES (?,?,?,?,?,?)", crews)

    # Load readings: 24 hourly readings per feeder; F-114 spikes 38% on the
    # last reading (the anomaly anchor).
    rid = 1
    for feeder_id, _, _, _, baseline in FEEDERS:
        for h in range(24):
            jitter = rng.uniform(-0.06, 0.06)
            mw = baseline * (1.0 + jitter)
            if feeder_id == "F-114" and h == 23:
                mw = baseline * 1.38
            cur.execute(
                "INSERT INTO load_readings VALUES (?,?,?,?,?)",
                (rid, feeder_id, f"2026-10-18T{h:02d}:00:00Z",
                 round(mw, 2), baseline),
            )
            rid += 1

    con.commit()
    con.close()
    return path
