from flask import Flask, render_template, request, redirect, jsonify
from datetime import datetime
from uuid import uuid4
from werkzeug.exceptions import BadRequest
import os
from database import get_db_connection, create_tables

app = Flask(__name__)

create_tables()
if os.environ.get('SEED_DEMO_DATA', '1') == '1':
    from demo import seed_demo
    seed_demo()


@app.context_processor
def scanner_prescriptions():
    connection = get_db_connection()
    prescriptions = connection.execute('''SELECT t.id, t.medicine_name, t.scheduled_time,
        p.patient_id AS patient_code, p.name AS patient_name FROM treatments t
        JOIN patients p ON p.id=t.patient_id ORDER BY lower(p.patient_id), t.id DESC''').fetchall()
    connection.close()
    return {'verification_prescriptions': prescriptions, 'online_prototype': bool(os.environ.get('VERCEL'))}


# =========================================================
# TIME HELPER
# =========================================================

def convert_to_24_hour(hour, minute, period):
    try:
        hour = int(hour)
        minute = int(minute)
    except (ValueError, TypeError):
        raise BadRequest('Select a valid scheduled time.')

    if not 1 <= hour <= 12 or not 0 <= minute <= 59 or period not in ('AM', 'PM'):
        raise BadRequest('Select a valid scheduled time.')

    if period == "AM":
        if hour == 12:
            hour = 0
    else:
        if hour != 12:
            hour += 12

    return f"{hour:02d}:{minute:02d}"


def convert_to_12_hour(time_string):
    if not time_string:
        return "", "", ""

    parts = time_string.split(":")

    hour = int(parts[0])
    minute = parts[1]

    period = "AM" if hour < 12 else "PM"

    display_hour = hour % 12

    if display_hour == 0:
        display_hour = 12

    return str(display_hour), minute, period


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return render_template("index.html")


# =========================================================
# ADD PATIENT
# =========================================================

@app.route("/add-patient", methods=["GET", "POST"])
def add_patient():

    if request.method == "POST":

        patient_id = request.form["patient_id"].strip()
        name = request.form["name"].strip()
        age = request.form["age"]
        gender = request.form["gender"]
        blood_group = request.form["blood_group"]
        contact = request.form["contact"].strip()
        admission_date = request.form["admission_date"]
        ward = request.form["ward"].strip()
        bed = request.form["bed"].strip()

        connection = get_db_connection()

        existing = connection.execute(
            "SELECT id FROM patients WHERE patient_id = ?",
            (patient_id,)
        ).fetchone()

        if existing:
            connection.close()

            return render_template(
                "add_patient.html",
                error="Patient ID already exists."
            )

        connection.execute("""
            INSERT INTO patients
            (
                patient_id,
                name,
                age,
                gender,
                blood_group,
                contact,
                admission_date,
                ward,
                bed
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            patient_id,
            name,
            age,
            gender,
            blood_group,
            contact,
            admission_date,
            ward,
            bed
        ))

        connection.commit()
        connection.close()

        return redirect("/patients")

    return render_template("add_patient.html")


# =========================================================
# PATIENT LIST
# =========================================================

@app.route("/patients")
def patients():

    connection = get_db_connection()

    patients = connection.execute("""
        SELECT *
        FROM patients
        ORDER BY id DESC
    """).fetchall()

    connection.close()

    return render_template(
        "patient.html",
        patients=patients
    )


# =========================================================
# PATIENT DASHBOARD
# =========================================================

@app.route("/patient/<int:patient_id>")
def patient_dashboard(patient_id):

    connection = get_db_connection()

    patient = connection.execute("""
        SELECT *
        FROM patients
        WHERE id = ?
    """, (patient_id,)).fetchone()

    if patient is None:
        connection.close()
        return "Patient not found", 404

    medical_history = connection.execute("""
        SELECT *
        FROM medical_history
        WHERE patient_id = ?
    """, (patient_id,)).fetchone()

    treatments = connection.execute("""
        SELECT *
        FROM treatments
        WHERE patient_id = ?
        ORDER BY id DESC
    """, (patient_id,)).fetchall()

    vitals = connection.execute("""
        SELECT *
        FROM vitals
        WHERE patient_id = ?
        ORDER BY id DESC
    """, (patient_id,)).fetchall()

    medicines = connection.execute('SELECT * FROM medicines ORDER BY medicine_name').fetchall()

    connection.close()

    return render_template(
        "patient_dashboard.html",
        patient=patient,
        medical_history=medical_history,
        treatments=treatments,
        vitals=vitals,
        medicines=medicines
    )


# =========================================================
# SAVE MEDICAL HISTORY
# =========================================================

@app.route(
    "/patient/<int:patient_id>/medical-history",
    methods=["POST"]
)
def save_medical_history(patient_id):

    previous_history = request.form["previous_history"].strip()
    allergies = request.form["allergies"].strip()

    connection = get_db_connection()

    existing = connection.execute("""
        SELECT id
        FROM medical_history
        WHERE patient_id = ?
    """, (patient_id,)).fetchone()

    if existing:

        connection.execute("""
            UPDATE medical_history
            SET previous_history = ?,
                allergies = ?
            WHERE patient_id = ?
        """, (
            previous_history,
            allergies,
            patient_id
        ))

    else:

        connection.execute("""
            INSERT INTO medical_history
            (
                patient_id,
                previous_history,
                allergies
            )
            VALUES (?, ?, ?)
        """, (
            patient_id,
            previous_history,
            allergies
        ))

    connection.commit()
    connection.close()

    return redirect(f"/patient/{patient_id}")


# =========================================================
# ADD TREATMENT
# =========================================================

@app.route(
    "/patient/<int:patient_id>/treatment",
    methods=["POST"]
)
def add_treatment(patient_id):

    medicine_id = request.form.get("medicine_id")
    medicine_type = request.form["medicine_type"]
    medicine_name = request.form["medicine_name"].strip()
    dose = request.form["dose"].strip()
    route = request.form["route"]

    hour = request.form["schedule_hour"]
    minute = request.form["schedule_minute"]
    period = request.form["schedule_period"]

    scheduled_time = convert_to_24_hour(
        hour,
        minute,
        period
    )

    connection = get_db_connection()

    patient = connection.execute("""
        SELECT id
        FROM patients
        WHERE id = ?
    """, (patient_id,)).fetchone()

    if patient is None:
        connection.close()
        return "Patient not found", 404

    if not medicine_id:
        medicine_id = None
    else:
        medicine = connection.execute('SELECT * FROM medicines WHERE id = ?', (medicine_id,)).fetchone()
        if medicine is None:
            connection.close()
            return 'Medicine not found', 400
        medicine_name = medicine['medicine_name']
        medicine_type = medicine['medicine_type']

    connection.execute("""
        INSERT INTO treatments
        (
            patient_id,
            medicine_id,
            medicine_type,
            medicine_name,
            dose,
            route,
            scheduled_time,
            status,
            given_at,
            missed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', NULL, NULL)
    """, (
        patient_id,
        medicine_id,
        medicine_type,
        medicine_name,
        dose,
        route,
        scheduled_time
    ))

    connection.commit()
    connection.close()

    return redirect(f"/patient/{patient_id}")


# =========================================================
# EDIT TREATMENT
# =========================================================

@app.route(
    "/treatment/<int:treatment_id>/edit",
    methods=["GET", "POST"]
)
def edit_treatment(treatment_id):

    connection = get_db_connection()

    treatment = connection.execute("""
        SELECT *
        FROM treatments
        WHERE id = ?
    """, (treatment_id,)).fetchone()

    if treatment is None:
        connection.close()
        return "Treatment not found", 404

    patient = connection.execute("""
        SELECT *
        FROM patients
        WHERE id = ?
    """, (treatment["patient_id"],)).fetchone()

    if request.method == "POST":

        medicine_type = request.form["medicine_type"]
        medicine_name = request.form["medicine_name"].strip()
        dose = request.form["dose"].strip()
        route = request.form["route"]

        hour = request.form["schedule_hour"]
        minute = request.form["schedule_minute"]
        period = request.form["schedule_period"]

        scheduled_time = convert_to_24_hour(
            hour,
            minute,
            period
        )

        connection.execute("""
            UPDATE treatments
            SET medicine_id = NULL,
                medicine_type = ?,
                medicine_name = ?,
                dose = ?,
                route = ?,
                scheduled_time = ?
            WHERE id = ?
        """, (
            medicine_type,
            medicine_name,
            dose,
            route,
            scheduled_time,
            treatment_id
        ))

        connection.commit()
        connection.close()

        return redirect(
            f"/patient/{treatment['patient_id']}"
        )

    hour, minute, period = convert_to_12_hour(
        treatment["scheduled_time"]
    )

    connection.close()

    return render_template(
        "edit_treatment.html",
        treatment=treatment,
        patient=patient,
        selected_hour=hour,
        selected_minute=minute,
        selected_period=period
    )


# =========================================================
# ADD VITAL
# =========================================================

@app.route(
    "/patient/<int:patient_id>/vitals",
    methods=["POST"]
)
def add_vital(patient_id):

    bp = request.form["bp"].strip()
    pulse = request.form["pulse"]
    spo2 = request.form["spo2"]
    temperature = request.form["temperature"]
    recorded_at = request.form["recorded_at"]

    connection = get_db_connection()

    connection.execute("""
        INSERT INTO vitals
        (
            patient_id,
            bp,
            pulse,
            spo2,
            temperature,
            recorded_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        patient_id,
        bp,
        pulse,
        spo2,
        temperature,
        recorded_at
    ))

    connection.commit()
    connection.close()

    return redirect(f"/patient/{patient_id}")


# =========================================================
# DELETE PATIENT
# =========================================================

@app.route(
    "/delete-patient/<int:patient_id>",
    methods=["POST"]
)
def delete_patient(patient_id):

    connection = get_db_connection()

    connection.execute("""
        DELETE FROM medical_history
        WHERE patient_id = ?
    """, (patient_id,))

    connection.execute("""
        DELETE FROM treatments
        WHERE patient_id = ?
    """, (patient_id,))

    connection.execute("""
        DELETE FROM vitals
        WHERE patient_id = ?
    """, (patient_id,))

    connection.execute("""
        DELETE FROM patients
        WHERE id = ?
    """, (patient_id,))

    connection.commit()
    connection.close()

    return redirect("/patients")


# =========================================================
# MARK GIVEN
# =========================================================

@app.route(
    "/treatment/<int:treatment_id>/given",
    methods=["POST"]
)
def mark_treatment_given(treatment_id):

    connection = get_db_connection()

    given_time = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    connection.execute("""
        UPDATE treatments
        SET status = 'Given',
            given_at = ?,
            missed_at = NULL
        WHERE id = ?
    """, (
        given_time,
        treatment_id
    ))

    connection.commit()
    connection.close()

    return jsonify({
        "success": True,
        "status": "Given",
        "given_at": given_time
    })


# =========================================================
# MARK MISSED
# =========================================================

@app.route(
    "/treatment/<int:treatment_id>/missed",
    methods=["POST"]
)
def mark_treatment_missed(treatment_id):

    connection = get_db_connection()

    missed_time = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    connection.execute("""
        UPDATE treatments
        SET status = 'Missed',
            missed_at = ?,
            given_at = NULL
        WHERE id = ?
    """, (
        missed_time,
        treatment_id
    ))

    connection.commit()
    connection.close()

    return jsonify({
        "success": True,
        "status": "Missed",
        "missed_at": missed_time
    })


# =========================================================
# RESET TO PENDING
# =========================================================

@app.route(
    "/treatment/<int:treatment_id>/pending",
    methods=["POST"]
)
def mark_treatment_pending(treatment_id):

    connection = get_db_connection()

    connection.execute("""
        UPDATE treatments
        SET status = 'Pending',
            given_at = NULL,
            missed_at = NULL
        WHERE id = ?
    """, (treatment_id,))

    connection.commit()
    connection.close()

    return jsonify({
        "success": True,
        "status": "Pending"
    })


# =========================================================
# REMINDERS
# =========================================================

@app.route("/reminders")
def reminders():

    connection = get_db_connection()

    treatments = connection.execute("""
        SELECT
            treatments.*,
            patients.patient_id AS patient_code,
            patients.name AS patient_name,
            patients.ward,
            patients.bed
        FROM treatments
        INNER JOIN patients
            ON treatments.patient_id = patients.id
        ORDER BY treatments.scheduled_time ASC
    """).fetchall()

    connection.close()

    return render_template(
        "reminders.html",
        treatments=treatments
    )


# =========================================================
# MEDICINES
# =========================================================

@app.route("/medicines")
def medicines():

    connection = get_db_connection()

    medicines = connection.execute("""
        SELECT *
        FROM medicines
        ORDER BY id DESC
    """).fetchall()

    connection.close()

    return render_template(
        "medicine.html",
        medicines=medicines
    )


# =========================================================
# ADD MEDICINE
# =========================================================

@app.route("/add-medicine", methods=["GET", "POST"])
def add_medicine():

    if request.method == "POST":

        barcode = request.form.get("barcode", "").strip() or 'MED-' + uuid4().hex[:16].upper()
        medicine_name = request.form["medicine_name"].strip()
        medicine_type = request.form["medicine_type"]
        dose = request.form["dose"].strip()
        route = request.form["route"]

        details = request.form.get('details', '').strip()
        manufacturing_date = request.form.get('manufacturing_date', '')
        expiry_date = request.form.get('expiry_date', '')
        try:
            manufactured = datetime.strptime(manufacturing_date, '%Y-%m-%d').date()
            expires = datetime.strptime(expiry_date, '%Y-%m-%d').date()
            if (not medicine_name or not medicine_type or expires < manufactured
                    or len(barcode) > 64 or any(ord(char) < 32 or ord(char) > 126 for char in barcode)):
                raise ValueError()
        except ValueError:
            connection = get_db_connection()
            medicines = connection.execute('SELECT * FROM medicines ORDER BY id DESC').fetchall()
            connection.close()
            return render_template('medicine.html', medicines=medicines,
                error='Enter a medicine name, type and valid dates. Expiry must not precede manufacturing. Barcodes must use up to 64 printable ASCII characters.'), 400

        connection = get_db_connection()

        existing = connection.execute("""
            SELECT id
            FROM medicines
            WHERE barcode = ?
        """, (barcode,)).fetchone()

        if existing:

            medicines = connection.execute("""
                SELECT *
                FROM medicines
                ORDER BY id DESC
            """).fetchall()

            connection.close()

            return render_template(
                "medicine.html",
                medicines=medicines,
                error="This barcode already exists."
            )

        connection.execute("""
            INSERT INTO medicines
            (
                barcode,
                medicine_name,
                medicine_type,
                dose,
                route,
                details,
                manufacturing_date,
                expiry_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            barcode,
            medicine_name,
            medicine_type,
            dose,
            route,
            details,
            manufacturing_date,
            expiry_date
        ))

        connection.commit()
        connection.close()

        return redirect("/medicines")

    connection = get_db_connection()

    medicines = connection.execute("""
        SELECT *
        FROM medicines
        ORDER BY id DESC
    """).fetchall()

    connection.close()

    return render_template(
        "medicine.html",
        medicines=medicines
    )


# =========================================================
# BARCODE LOOKUP
# =========================================================

@app.route("/api/medicine/<barcode>")
def medicine_lookup(barcode):

    connection = get_db_connection()

    medicine = connection.execute("""
        SELECT *
        FROM medicines
        WHERE barcode = ?
    """, (barcode.strip(),)).fetchone()

    connection.close()

    if medicine is None:
        return jsonify({
            "found": False,
            "message": "Medicine not found."
        }), 404

    return jsonify({
        "found": True,
        "id": medicine["id"],
        "barcode": medicine["barcode"],
        "medicine_name": medicine["medicine_name"],
        "medicine_type": medicine["medicine_type"],
        "dose": medicine["dose"],
        "route": medicine["route"],
        "details": medicine["details"],
        "manufacturing_date": medicine["manufacturing_date"],
        "expiry_date": medicine["expiry_date"]
    })


@app.route('/treatment/<int:treatment_id>/verify', methods=['GET', 'POST'])
def verify_medicine(treatment_id):
    connection = get_db_connection()
    treatment = connection.execute('SELECT * FROM treatments WHERE id = ?', (treatment_id,)).fetchone()
    if treatment is None:
        connection.close()
        return jsonify(message='Treatment not found.'), 404
    patient = connection.execute('SELECT * FROM patients WHERE id = ?', (treatment['patient_id'],)).fetchone()
    if patient is None:
        connection.close()
        return jsonify(message='Patient not found.'), 404
    if request.method == 'GET':
        connection.close()
        return render_template('verify_medicine.html', treatment=treatment, patient=patient)
    payload = request.get_json(silent=True)
    barcode = payload.get('barcode') if isinstance(payload, dict) else request.form.get('barcode')
    if not isinstance(barcode, str) or not barcode.strip():
        connection.close()
        return jsonify(verified=False, message='Scan or enter a barcode.'), 400
    medicine = connection.execute('SELECT * FROM medicines WHERE barcode = ?', (barcode.strip(),)).fetchone()
    connection.close()
    if medicine is None:
        return jsonify(verified=False, message='Unknown barcode — medicine not registered.'), 404
    normalize = lambda value: ' '.join((value or '').split()).casefold()
    # Compare the prescribed identity, never a client-supplied medicine name.
    matches = (normalize(medicine['medicine_name']) == normalize(treatment['medicine_name'])
        and (not treatment['medicine_type'] or normalize(medicine['medicine_type']) == normalize(treatment['medicine_type'])))
    return jsonify(verified=matches,
        message='Verified — Correct Medicine.' if matches else 'Wrong Medicine.',
        medicine=dict(medicine), prescribed_medicine=treatment['medicine_name'],
        scheduled_time=treatment['scheduled_time'],
        expired=bool(medicine['expiry_date'] and medicine['expiry_date'] < datetime.now().strftime('%Y-%m-%d')))


@app.route('/medicine/<int:medicine_id>/label')
def medicine_label(medicine_id):
    connection = get_db_connection()
    medicine = connection.execute('SELECT * FROM medicines WHERE id = ?', (medicine_id,)).fetchone()
    connection.close()
    if medicine is None:
        return 'Medicine not found', 404
    return render_template('medicine_label.html', medicine=medicine)


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.environ.get('PORT', '5000')),
        debug=False
    )
