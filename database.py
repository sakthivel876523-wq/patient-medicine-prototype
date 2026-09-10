import sqlite3
import os
import tempfile
from pathlib import Path

DATABASE_NAME = os.environ.get('DATABASE_PATH') or str(
    Path(tempfile.gettempdir()) / 'patient-prototype.db' if os.environ.get('VERCEL')
    else Path(__file__).resolve().with_name('hospital.db'))


def get_db_connection():
    connection = sqlite3.connect(DATABASE_NAME, timeout=20)
    connection.row_factory = sqlite3.Row
    return connection


def create_tables():
    connection = get_db_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            age INTEGER,
            gender TEXT,
            blood_group TEXT,
            contact TEXT,
            admission_date TEXT,
            ward TEXT,
            bed TEXT
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS medical_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            previous_history TEXT,
            allergies TEXT,
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            barcode TEXT UNIQUE,
            medicine_name TEXT NOT NULL,
            medicine_type TEXT,
            dose TEXT,
            route TEXT
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS treatments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            medicine_id INTEGER,
            medicine_type TEXT,
            medicine_name TEXT NOT NULL,
            dose TEXT,
            route TEXT,
            scheduled_time TEXT,
            status TEXT DEFAULT 'Pending',
            given_at TEXT,
            missed_at TEXT,
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (medicine_id) REFERENCES medicines(id)
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS vitals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            bp TEXT,
            pulse INTEGER,
            spo2 INTEGER,
            temperature REAL,
            recorded_at TEXT,
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )
    """)

    # Add columns when using your existing database
    columns = connection.execute(
        "PRAGMA table_info(treatments)"
    ).fetchall()

    column_names = [column["name"] for column in columns]

    if "medicine_type" not in column_names:
        connection.execute("""
            ALTER TABLE treatments
            ADD COLUMN medicine_type TEXT
        """)

    if "given_at" not in column_names:
        connection.execute("""
            ALTER TABLE treatments
            ADD COLUMN given_at TEXT
        """)

    if "missed_at" not in column_names:
        connection.execute("""
            ALTER TABLE treatments
            ADD COLUMN missed_at TEXT
        """)

    medicine_columns = {row['name'] for row in connection.execute('PRAGMA table_info(medicines)')}
    for column in ('details', 'manufacturing_date', 'expiry_date'):
        if column not in medicine_columns:
            connection.execute(f'ALTER TABLE medicines ADD COLUMN {column} TEXT')

    connection.commit()
    connection.close()


if __name__ == "__main__":
    create_tables()
    print("Database and tables created successfully!")
