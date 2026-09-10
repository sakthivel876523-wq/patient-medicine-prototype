"""Default presentation fixtures shared by normal and demo startup."""
from pathlib import Path
import database


def seed_demo():
    database.create_tables()
    connection = database.get_db_connection()
    for barcode, name in [('DEMO-PARA-001', 'Paracetamol'), ('DEMO-MED-002', 'Demo Medicine B')]:
        connection.execute('''INSERT OR IGNORE INTO medicines
            (barcode, medicine_name, medicine_type, dose, route, details, manufacturing_date, expiry_date)
            VALUES (?, ?, 'Tablet', 'Demo strength', 'Oral',
            'DEMONSTRATION ONLY. Fictional packaging dates and strength; not for patient use.',
            '2026-01-01', '2028-01-01')''', (barcode, name))
    # Upgrade the earlier one-patient presentation when present.
    legacy_demo = connection.execute("SELECT id FROM patients WHERE patient_id='DEMO-PATIENT'").fetchone()
    connection.execute("""UPDATE patients SET patient_id='P1', name='ariharan'
        WHERE patient_id='DEMO-PATIENT'
        AND NOT EXISTS (SELECT 1 FROM patients WHERE patient_id='P1')""")
    assignments = [('P1', 'ariharan', 'DEMO-PARA-001', '1'),
                   ('P2', 'aran', 'DEMO-MED-002', '2')]
    for code, name, barcode, bed in assignments:
        patient = connection.execute('SELECT id FROM patients WHERE lower(patient_id)=lower(?)', (code,)).fetchone()
        if patient is None:
            cursor = connection.execute('''INSERT INTO patients
                (patient_id, name, age, gender, blood_group, contact, admission_date, ward, bed)
                VALUES (?, ?, 30, 'Other', 'Not recorded', '', '2026-09-09', 'Demo Ward', ?)''',
                (code, name, bed))
            patient_id = cursor.lastrowid
        else:
            patient_id = patient['id']
        medicine = connection.execute('SELECT * FROM medicines WHERE barcode=?', (barcode,)).fetchone()
        if code == 'P2' and legacy_demo:
            connection.execute('''UPDATE treatments SET patient_id=? WHERE medicine_id=?
                AND patient_id=(SELECT id FROM patients WHERE patient_id='P1')''',
                (patient_id, medicine['id']))
        existing = connection.execute('SELECT id FROM treatments WHERE patient_id=? AND medicine_id=?',
            (patient_id, medicine['id'])).fetchone()
        if not existing:
            connection.execute('''INSERT INTO treatments
                (patient_id, medicine_id, medicine_name, medicine_type, dose, route, scheduled_time)
                VALUES (?, ?, ?, 'Tablet', 'Demo strength', 'Oral', '21:00')''',
                (patient_id, medicine['id'], medicine['medicine_name']))
    connection.commit()
    connection.close()


def create_demo_app():
    database.DATABASE_NAME = str(Path(__file__).with_name('demo-hospital.db'))
    from app import app
    seed_demo()
    return app


if __name__ == '__main__':
    create_demo_app().run(host='127.0.0.1', port=5001, debug=False)
