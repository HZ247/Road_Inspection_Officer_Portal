import sqlite3
import bcrypt
import os
import json

DB_PATH = os.path.join(os.path.dirname(__file__), 'data.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    # ── Users ────────────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT NOT NULL,
            employee_id  TEXT UNIQUE NOT NULL,
            designation  TEXT,
            department   TEXT,
            mobile       TEXT,
            password     TEXT NOT NULL,
            role         TEXT DEFAULT 'fvo',
            otp_verified INTEGER DEFAULT 0,
            created_at   TEXT DEFAULT (datetime('now'))
        )
    ''')

    # ── Attendance ───────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            employee_id   TEXT NOT NULL,
            checkin_time  TEXT,
            checkin_lat   REAL,
            checkin_lng   REAL,
            checkout_time TEXT,
            checkout_lat  REAL,
            checkout_lng  REAL,
            duration_mins INTEGER,
            date          TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # ── Inspections ──────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS inspections (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER NOT NULL,
            employee_id      TEXT NOT NULL,
            site_name        TEXT NOT NULL,
            road_name        TEXT NOT NULL,
            contract_id      TEXT,
            start_time       TEXT,
            end_time         TEXT,
            start_lat        REAL,
            start_lng        REAL,
            gps_trail        TEXT,
            photo_count      INTEGER DEFAULT 0,
            coverage_percent INTEGER DEFAULT 0,
            remarks          TEXT,
            admin_remarks    TEXT,
            status           TEXT DEFAULT 'active',
            date             TEXT,
            created_at       TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # ── Inspection Photos ────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS inspection_photos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            inspection_id INTEGER NOT NULL,
            filename      TEXT NOT NULL,
            lat           REAL,
            lng           REAL,
            captured_at   TEXT,
            sequence      INTEGER,
            FOREIGN KEY (inspection_id) REFERENCES inspections(id)
        )
    ''')

    # ── Contracts (dummy seeded) ─────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS contracts (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            contract_id   TEXT UNIQUE NOT NULL,
            project_name  TEXT NOT NULL,
            location      TEXT,
            contractor    TEXT,
            start_date    TEXT,
            end_date      TEXT,
            total_value   REAL
        )
    ''')

    # ── Contract Materials (items per contract) ──────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS contract_materials (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            contract_id   TEXT NOT NULL,
            category      TEXT NOT NULL,
            item_name     TEXT NOT NULL,
            unit          TEXT NOT NULL,
            qty_contracted REAL NOT NULL,
            FOREIGN KEY (contract_id) REFERENCES contracts(contract_id)
        )
    ''')

    # ── Material Check Submissions ───────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS material_checks (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            employee_id   TEXT NOT NULL,
            contract_id   TEXT NOT NULL,
            date          TEXT NOT NULL,
            gps_lat       REAL,
            gps_lng       REAL,
            overall_status TEXT DEFAULT 'ok',
            remarks       TEXT,
            admin_remarks TEXT,
            status        TEXT DEFAULT 'submitted',
            items_json    TEXT,
            created_at    TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # ── Seed admin ───────────────────────────────────────────
    existing_admin = c.execute(
        'SELECT id FROM users WHERE employee_id = ?', ('ADMIN001',)
    ).fetchone()
    if not existing_admin:
        hashed = bcrypt.hashpw('admin123'.encode(), bcrypt.gensalt()).decode()
        c.execute('''
            INSERT INTO users
              (name, employee_id, designation, department, mobile, password, role, otp_verified)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('Admin User', 'ADMIN001', 'Administrator',
              'Admin Dept', '9000000000', hashed, 'admin', 1))
        print('✅ Admin seeded — ID: ADMIN001 | Password: admin123')

    # ── Seed contracts + materials (only once) ───────────────
    existing_contract = c.execute(
        'SELECT id FROM contracts WHERE contract_id = ?', ('C-2024-RH-001',)
    ).fetchone()

    if not existing_contract:
        contracts = [
            ('C-2024-RH-001', 'Surat Ring Road Phase 2',
             'Surat, Gujarat', 'Mehta Constructions Pvt Ltd',
             '2024-01-15', '2025-06-30', 18500000),
            ('C-2024-RH-002', 'Tapi Bridge Approach Road',
             'Tapi District, Gujarat', 'Gujarat Infra Works',
             '2024-03-01', '2025-03-31', 9200000),
            ('C-2024-RH-003', 'Hazira Industrial Connector',
             'Hazira, Surat', 'Coastal Builders Ltd',
             '2024-02-10', '2025-08-15', 14700000),
            ('C-2024-RH-004', 'Udhna–Sachin Corridor',
             'Udhna to Sachin, Surat', 'Apex Road Projects',
             '2024-04-01', '2025-12-31', 22100000),
        ]
        c.executemany('''
            INSERT INTO contracts
              (contract_id, project_name, location, contractor,
               start_date, end_date, total_value)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', contracts)

        materials = [
            # C-2024-RH-001
            ('C-2024-RH-001', 'Bituminous Material', 'Bitumen VG-30',        'MT',    85.0),
            ('C-2024-RH-001', 'Bituminous Material', 'Dense Bituminous Macadam (DBM)', 'MT', 420.0),
            ('C-2024-RH-001', 'Bituminous Material', 'Bituminous Concrete (BC)',       'MT', 210.0),
            ('C-2024-RH-001', 'Aggregates',          'Coarse Aggregate 40mm', 'CUM',  350.0),
            ('C-2024-RH-001', 'Aggregates',          'Fine Aggregate',        'CUM',  180.0),
            ('C-2024-RH-001', 'Aggregates',          'Stone Chips 12mm',      'CUM',   95.0),
            ('C-2024-RH-001', 'Equipment',           'Paver Machine',         'Nos',    1.0),
            ('C-2024-RH-001', 'Equipment',           'Tandem Roller',         'Nos',    2.0),
            ('C-2024-RH-001', 'Equipment',           'Pneumatic Tyre Roller', 'Nos',    1.0),
            ('C-2024-RH-001', 'Equipment',           'Bitumen Sprayer',       'Nos',    1.0),
            ('C-2024-RH-001', 'Labour',              'Skilled Workers',       'Nos',   18.0),
            ('C-2024-RH-001', 'Labour',              'Unskilled Workers',     'Nos',   35.0),

            # C-2024-RH-002
            ('C-2024-RH-002', 'Bituminous Material', 'Bitumen VG-30',        'MT',    42.0),
            ('C-2024-RH-002', 'Bituminous Material', 'Dense Bituminous Macadam (DBM)', 'MT', 195.0),
            ('C-2024-RH-002', 'Bituminous Material', 'Bituminous Concrete (BC)',       'MT',  98.0),
            ('C-2024-RH-002', 'Aggregates',          'Coarse Aggregate 40mm', 'CUM',  160.0),
            ('C-2024-RH-002', 'Aggregates',          'Fine Aggregate',        'CUM',   85.0),
            ('C-2024-RH-002', 'Equipment',           'Paver Machine',         'Nos',    1.0),
            ('C-2024-RH-002', 'Equipment',           'Tandem Roller',         'Nos',    1.0),
            ('C-2024-RH-002', 'Equipment',           'Concrete Mixer',        'Nos',    2.0),
            ('C-2024-RH-002', 'Labour',              'Skilled Workers',       'Nos',   12.0),
            ('C-2024-RH-002', 'Labour',              'Unskilled Workers',     'Nos',   20.0),

            # C-2024-RH-003
            ('C-2024-RH-003', 'Bituminous Material', 'Bitumen VG-40',        'MT',    65.0),
            ('C-2024-RH-003', 'Bituminous Material', 'Dense Bituminous Macadam (DBM)', 'MT', 310.0),
            ('C-2024-RH-003', 'Aggregates',          'Coarse Aggregate 40mm', 'CUM',  275.0),
            ('C-2024-RH-003', 'Aggregates',          'Stone Chips 12mm',      'CUM',   70.0),
            ('C-2024-RH-003', 'Equipment',           'Paver Machine',         'Nos',    2.0),
            ('C-2024-RH-003', 'Equipment',           'Motor Grader',          'Nos',    1.0),
            ('C-2024-RH-003', 'Equipment',           'Tandem Roller',         'Nos',    2.0),
            ('C-2024-RH-003', 'Labour',              'Skilled Workers',       'Nos',   22.0),
            ('C-2024-RH-003', 'Labour',              'Unskilled Workers',     'Nos',   40.0),

            # C-2024-RH-004
            ('C-2024-RH-004', 'Bituminous Material', 'Bitumen VG-30',        'MT',   110.0),
            ('C-2024-RH-004', 'Bituminous Material', 'Dense Bituminous Macadam (DBM)', 'MT', 540.0),
            ('C-2024-RH-004', 'Bituminous Material', 'Bituminous Concrete (BC)',       'MT', 270.0),
            ('C-2024-RH-004', 'Aggregates',          'Coarse Aggregate 40mm', 'CUM',  450.0),
            ('C-2024-RH-004', 'Aggregates',          'Fine Aggregate',        'CUM',  220.0),
            ('C-2024-RH-004', 'Aggregates',          'Stone Chips 12mm',      'CUM',  120.0),
            ('C-2024-RH-004', 'Equipment',           'Paver Machine',         'Nos',    2.0),
            ('C-2024-RH-004', 'Equipment',           'Tandem Roller',         'Nos',    3.0),
            ('C-2024-RH-004', 'Equipment',           'Pneumatic Tyre Roller', 'Nos',    2.0),
            ('C-2024-RH-004', 'Equipment',           'Motor Grader',          'Nos',    1.0),
            ('C-2024-RH-004', 'Labour',              'Skilled Workers',       'Nos',   28.0),
            ('C-2024-RH-004', 'Labour',              'Unskilled Workers',     'Nos',   55.0),
        ]
        c.executemany('''
            INSERT INTO contract_materials
              (contract_id, category, item_name, unit, qty_contracted)
            VALUES (?, ?, ?, ?, ?)
        ''', materials)

        print('✅ Contracts + materials seeded (4 contracts)')

    conn.commit()
    conn.close()