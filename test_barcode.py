import importlib
from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path
import database


class BarcodeWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.original_db = database.DATABASE_NAME
        database.DATABASE_NAME = str(Path(cls.folder.name) / 'test.db')
        cls.module = importlib.import_module('app')
        from demo import seed_demo
        seed_demo()
        cls.module.app.config['TESTING'] = True
        cls.client = cls.module.app.test_client()

    @classmethod
    def tearDownClass(cls):
        database.DATABASE_NAME = cls.original_db
        cls.folder.cleanup()

    def test_matching_and_wrong_medicine(self):
        for barcode, expected in [('DEMO-PARA-001', True), ('DEMO-MED-002', False)]:
            result = self.client.post('/treatment/1/verify', json={'barcode': barcode})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json['verified'], expected)
            self.assertEqual(result.json['message'], 'Verified — Correct Medicine.' if expected else 'Wrong Medicine.')
            self.assertIn('manufacturing_date', result.json['medicine'])
        with closing(database.get_db_connection()) as connection:
            self.assertEqual(connection.execute('SELECT status FROM treatments WHERE id=1').fetchone()[0], 'Pending')

    def test_demo_has_one_prescription_per_patient(self):
        from demo import seed_demo
        seed_demo()
        with closing(database.get_db_connection()) as connection:
            rows = connection.execute('''SELECT patients.patient_id, medicines.barcode
                FROM patients JOIN treatments ON patients.id=treatments.patient_id
                JOIN medicines ON treatments.medicine_id=medicines.id ORDER BY patients.id''').fetchall()
            self.assertEqual([tuple(row) for row in rows], [('P1','DEMO-PARA-001'), ('P2','DEMO-MED-002')])
        for treatment_id, barcode, expected in [(1,'DEMO-PARA-001',True), (1,'DEMO-MED-002',False),
                (2,'DEMO-MED-002',True), (2,'DEMO-PARA-001',False)]:
            result = self.client.post(f'/treatment/{treatment_id}/verify', json={'barcode':barcode})
            self.assertEqual(result.json['verified'], expected)

    def test_normal_pages_have_defaults_and_all_features(self):
        home = self.client.get('/').get_data(as_text=True)
        for link in ('/patients', '/medicines', '/reminders'):
            self.assertIn(link, home)
        for patient_id, name, medicine in [(1,'ariharan','Paracetamol'), (2,'aran','Demo Medicine B')]:
            page = self.client.get(f'/patient/{patient_id}').get_data(as_text=True)
            for expected in (name, medicine, "Doctor's Prescription", 'id="startScannerButton"',
                    f'/treatment/{patient_id}/verify', 'Medical History', 'Vital History', '/static/vendor/html5-qrcode.min.js'):
                self.assertIn(expected, page)
        medicine_page = self.client.get('/medicines').get_data(as_text=True)
        self.assertIn('id="verificationTreatment"', medicine_page)
        self.assertIn('DEMO-PARA-001', medicine_page)
        self.assertIn('DEMO-MED-002', medicine_page)

    def test_unknown_missing_and_invalid_requests(self):
        self.assertEqual(self.client.post('/treatment/1/verify', json={'barcode': 'unknown'}).status_code, 404)
        self.assertEqual(self.client.post('/treatment/999/verify', json={'barcode': 'DEMO-PARA-001'}).status_code, 404)
        for payload in ({}, {'barcode': 123}, [], {'barcode': ' '}):
            self.assertEqual(self.client.post('/treatment/1/verify', json=payload).status_code, 400)

    def test_another_batch_and_expiry_warning(self):
        with closing(database.get_db_connection()) as connection:
            connection.execute('''INSERT INTO medicines (barcode, medicine_name, medicine_type, expiry_date)
                VALUES ('OLD-PARA-BATCH', 'Paracetamol', 'Tablet', '2000-01-01')''')
            connection.commit()
        result = self.client.post('/treatment/1/verify', json={'barcode':'OLD-PARA-BATCH'})
        self.assertTrue(result.json['verified'])
        self.assertTrue(result.json['expired'])

    def test_editing_prescription_changes_verification(self):
        data = dict(medicine_name='Paracetamol', medicine_type='Tablet', dose='test', route='Oral',
            schedule_hour='9', schedule_minute='00', schedule_period='PM', medicine_id='1')
        self.client.post('/patient/1/treatment', data=data)
        with closing(database.get_db_connection()) as connection:
            treatment_id = connection.execute('SELECT MAX(id) FROM treatments').fetchone()[0]
        data['medicine_name'] = 'Demo Medicine B'
        self.assertEqual(self.client.post(f'/treatment/{treatment_id}/edit', data=data).status_code, 302)
        self.assertFalse(self.client.post(f'/treatment/{treatment_id}/verify', json={'barcode':'DEMO-PARA-001'}).json['verified'])
        self.assertTrue(self.client.post(f'/treatment/{treatment_id}/verify', json={'barcode':'DEMO-MED-002'}).json['verified'])

    def test_registration_lookup_and_dates(self):
        data = dict(barcode='', medicine_name='Test medicine', medicine_type='Tablet', dose='Test strength',
            route='Oral', details='Test details', manufacturing_date='2026-01-01', expiry_date='2027-01-01')
        self.assertEqual(self.client.post('/add-medicine', data=data).status_code, 302)
        with closing(database.get_db_connection()) as connection:
            row = connection.execute("SELECT * FROM medicines WHERE medicine_name='Test medicine'").fetchone()
            barcode = row['barcode']
        self.assertTrue(barcode.startswith('MED-'))
        result = self.client.get('/api/medicine/' + barcode)
        self.assertEqual(result.json['details'], 'Test details')
        self.assertEqual(result.json['expiry_date'], '2027-01-01')
        data['expiry_date'] = '2025-01-01'
        self.assertEqual(self.client.post('/add-medicine', data=data).status_code, 400)

    def test_pages_render(self):
        for path in ('/', '/medicines', '/patients', '/patient/1', '/reminders', '/treatment/1/verify', '/medicine/1/label'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_legacy_prescription_and_server_identity(self):
        data = dict(medicine_name='  PARACETAMOL ', medicine_type='Tablet', dose='test', route='Oral',
            schedule_hour='9', schedule_minute='00', schedule_period='PM')
        self.assertEqual(self.client.post('/patient/1/treatment', data=data).status_code, 302)
        with closing(database.get_db_connection()) as connection:
            treatment_id = connection.execute('SELECT MAX(id) FROM treatments').fetchone()[0]
        self.assertTrue(self.client.post(f'/treatment/{treatment_id}/verify', json={'barcode':'DEMO-PARA-001'}).json['verified'])
        data.update(medicine_id='1', medicine_name='Tampered medicine')
        self.client.post('/patient/1/treatment', data=data)
        with closing(database.get_db_connection()) as connection:
            treatment = connection.execute('SELECT * FROM treatments ORDER BY id DESC LIMIT 1').fetchone()
            self.assertEqual(treatment['medicine_name'], 'Paracetamol')
            self.assertEqual(treatment['scheduled_time'], '21:00')
        data['schedule_hour'] = 'abc'
        self.assertEqual(self.client.post('/patient/1/treatment', data=data).status_code, 400)

    def test_migration_preserves_existing_medicines(self):
        original = database.DATABASE_NAME
        try:
            database.DATABASE_NAME = str(Path(self.folder.name) / 'legacy.db')
            with closing(sqlite3.connect(database.DATABASE_NAME)) as connection:
                connection.execute('CREATE TABLE medicines (id INTEGER PRIMARY KEY, barcode TEXT UNIQUE, medicine_name TEXT NOT NULL, medicine_type TEXT, dose TEXT, route TEXT)')
                connection.execute("INSERT INTO medicines VALUES (1,'OLD','Old Medicine','Tablet','test','Oral')")
                connection.commit()
            database.create_tables()
            database.create_tables()
            with closing(database.get_db_connection()) as connection:
                row = connection.execute('SELECT * FROM medicines').fetchone()
                self.assertEqual(row['medicine_name'], 'Old Medicine')
                self.assertIsNone(row['expiry_date'])
        finally:
            database.DATABASE_NAME = original


if __name__ == '__main__':
    unittest.main()
