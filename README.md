# Patient Medicine Verification Prototype

Full Flask application with patient registration and details, medical history, vitals, medicine management, doctor prescriptions, reminders, and camera barcode verification.

## Default presentation records

Normal startup seeds two demonstration prescriptions, without a separate demo mode:

- P1 / ariharan: Paracetamol, barcode `DEMO-PARA-001`.
- P2 / aran: Demo Medicine B, barcode `DEMO-MED-002`.

These are sample profiles and fictional prescriptions. No patient database, medical history, contact details, local backups or credentials are included in this repository.

## Run locally

Install Python 3.12 or later, then:

    python -m venv .venv
    .venv/Scripts/python -m pip install -r requirements.txt
    .venv/Scripts/python app.py

Open http://127.0.0.1:5000. Default records are inserted once if missing. Existing records are retained.

## Present the workflow

1. Open Patients, then View P1 or P2.
2. Read Doctor's Prescription and click Verify medicine with camera.
3. Click Start Barcode Scanner and allow camera permission.
4. Show the matching barcode: Verified — Correct Medicine.
5. Show the other barcode: Wrong Medicine.

The Medicine List & Checking page also lets you select a patient's prescription and scan. Decoding triggers verification automatically; no manual confirmation is needed. USB scanners, manual entry and image decoding are also supported.

PNG barcodes are in static/barcodes. Printable labels are available from the Medicines page. Camera access requires localhost or HTTPS. Use a printed barcode or a second device's screen.

## Hosting

GitHub stores this source. GitHub Pages alone cannot execute the Flask backend. This repository includes Vercel Flask configuration and a build script that places static assets in public/static.

On Vercel, SQLite uses the writable temporary directory and recreates the two default profiles on a fresh instance. This is a demonstration environment: edits may reset, are not durable across instances, and must not contain real patient data. Production use requires authentication and a persistent shared database.

## Tests

    python -m unittest -v test_barcode

Scanner and barcode libraries are vendored under static/vendor with their licenses.
