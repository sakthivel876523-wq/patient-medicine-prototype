let scanner = null;
let scanBusy = false;
let imageBusy = false;
const startButton = document.getElementById('startScannerButton');
const stopButton = document.getElementById('stopScannerButton');
const statusText = document.getElementById('scannerStatus');
const verification = document.getElementById('verification');

function showMedicine(medicine) {
    const list = document.getElementById('medicineDetails');
    if (!list) return;
    list.replaceChildren();
    const fields = {medicine_name:'Medicine', barcode:'Barcode', medicine_type:'Type', dose:'Dose / strength', route:'Route', details:'Details', manufacturing_date:'Manufacturing date', expiry_date:'Expiry date'};
    for (const [key, title] of Object.entries(fields)) {
        const term = document.createElement('dt');
        term.textContent = title;
        term.style.fontWeight = 'bold';
        const value = document.createElement('dd');
        value.textContent = medicine[key] || 'Not recorded';
        list.append(term, value);
    }
    document.getElementById('scannedDetails').hidden = false;
}

function fillMedicine(medicine) {
    for (const key of ['medicine_name', 'medicine_type', 'dose', 'route']) {
        const input = document.getElementById(key);
        if (input) input.value = medicine[key] || '';
    }
    const id = document.getElementById('medicine_id');
    if (id) id.value = medicine.id;
    const select = document.getElementById('registeredMedicine');
    if (select) select.value = String(medicine.id);
}

async function onBarcodeDetected(text) {
    if (scanBusy || !text.trim()) return;
    if (verification && !verification.dataset.url) {
        statusText.textContent = "Select the patient's prescription before scanning.";
        return;
    }
    scanBusy = true;
    statusText.textContent = 'Checking barcode...';
    statusText.style.color = '';
    const details = document.getElementById('scannedDetails');
    if (details) details.hidden = true;
    const warning = document.getElementById('expiryWarning');
    if (warning) warning.textContent = '';
    const selectedPrescription = verification?.dataset.url;
    try {
        const response = await fetch(verification ? verification.dataset.url : '/api/medicine/' + encodeURIComponent(text.trim()),
            verification ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({barcode:text.trim()})} : {});
        const data = await response.json();
        if (verification && verification.dataset.url !== selectedPrescription) return;
        if (verification) {
            statusText.textContent = data.message || 'Could not verify medicine.';
            statusText.style.color = response.ok && data.verified ? '#166534' : '#b91c1c';
            statusText.style.fontWeight = 'bold';
            if (data.medicine) showMedicine(data.medicine);
            if (warning && data.expired) {
                warning.textContent = 'Expired medicine — check the expiry date before administration.';
                warning.style.color = '#b91c1c';
            }
        } else if (response.ok && data.found) {
            showMedicine(data);
            // Registration lookup displays an existing medicine without overwriting the new medicine form.
            if (document.getElementById('medicine_id')) fillMedicine(data);
            statusText.textContent = 'Medicine found.';
        } else {
            statusText.textContent = data.message || 'Medicine not found.';
        }
        await stopScanner();
    } catch (error) {
        statusText.textContent = 'Could not check barcode. Check the connection and try again.';
    } finally {
        scanBusy = false;
    }
}

async function startScanner() {
    if (!startButton || startButton.disabled || scanner || imageBusy) return;
    startButton.disabled = true;
    try {
        if (typeof Html5Qrcode === 'undefined') throw new Error('Scanner library unavailable');
        if (!window.isSecureContext) throw new Error('InsecureContext');
        if (!navigator.mediaDevices?.getUserMedia) throw new Error('CameraApiUnavailable');
        const cameras = await Html5Qrcode.getCameras();
        if (!cameras.length) throw new Error('NotFoundError');
        const camera = cameras.find(device => /back|rear|environment/i.test(device.label)) || cameras[0];
        scanner = new Html5Qrcode('reader');
        await scanner.start(camera.id, {fps:10}, onBarcodeDetected, () => {});
        startButton.style.display = 'none';
        stopButton.style.display = 'inline-block';
        statusText.textContent = 'Point the camera at the medicine barcode.';
    } catch (error) {
        if (scanner) {
            try { scanner.clear(); } catch (_) {}
        }
        scanner = null;
        const reason = String(error?.name || '') + ' ' + String(error?.message || error);
        if (/library unavailable/i.test(reason)) {
            statusText.textContent = 'Scanner library did not load. Restart the app and reload the page. Manual barcode entry still works.';
        } else if (/InsecureContext|CameraApiUnavailable/i.test(reason)) {
            statusText.textContent = 'Camera access requires Chrome or Edge on http://localhost:5001 or HTTPS. Open the app in your browser, not the VS Code preview.';
        } else if (/NotAllowed|PermissionDenied|permission|denied/i.test(reason)) {
            statusText.textContent = 'Camera permission was blocked. Allow Camera in this browser’s site settings and Windows camera privacy settings, then try again.';
        } else if (/NotFound|DevicesNotFound|no camera/i.test(reason)) {
            statusText.textContent = 'No camera was detected. Connect a webcam, or choose a barcode image below.';
        } else if (/NotReadable|TrackStart|in use|could not start/i.test(reason)) {
            statusText.textContent = 'The camera could not be opened. Close other camera apps, check the webcam connection, and try again.';
        } else {
            statusText.textContent = 'Camera could not start: ' + reason + '. You can choose a barcode image below.';
        }
    } finally {
        startButton.disabled = false;
    }
}

document.getElementById('barcodeImage')?.addEventListener('change', async event => {
    const input = event.target;
    const file = input.files[0];
    if (!file || imageBusy || scanBusy || startButton?.disabled) return;
    imageBusy = true;
    input.disabled = true;
    await stopScanner();
    statusText.textContent = 'Reading barcode image...';
    statusText.style.color = '';
    document.getElementById('scannedDetails').hidden = true;
    const warning = document.getElementById('expiryWarning');
    if (warning) warning.textContent = '';
    let imageScanner;
    try {
        if (typeof Html5Qrcode === 'undefined') throw new Error('Scanner library unavailable');
        imageScanner = new Html5Qrcode('reader');
        const decoded = await imageScanner.scanFile(file, false);
        await onBarcodeDetected(decoded);
    } catch (error) {
        statusText.textContent = typeof Html5Qrcode === 'undefined'
            ? 'Scanner library did not load. Restart the app and reload, or enter the barcode manually.'
            : 'No readable barcode found. Select the original barcode PNG or a clear photo showing the entire barcode.';
    } finally {
        try { imageScanner?.clear(); } catch (_) {}
        imageBusy = false;
        input.disabled = false;
        input.value = '';
    }
});

async function stopScanner() {
    const current = scanner;
    scanner = null;
    if (current) {
        try { await current.stop(); current.clear(); } catch (_) {}
    }
    if (startButton) startButton.style.display = 'inline-block';
    if (stopButton) stopButton.style.display = 'none';
}
startButton?.addEventListener('click', startScanner);
stopButton?.addEventListener('click', stopScanner);
document.getElementById('verificationTreatment')?.addEventListener('change', async event => {
    await stopScanner();
    verification.dataset.url = event.target.value;
    statusText.textContent = '';
    document.getElementById('scannedDetails').hidden = true;
    const warning = document.getElementById('expiryWarning');
    if (warning) warning.textContent = '';
});
document.getElementById('manualScanForm')?.addEventListener('submit', event => {
    event.preventDefault();
    onBarcodeDetected(document.getElementById('scanBarcode').value);
});
document.getElementById('registeredMedicine')?.addEventListener('change', event => {
    const selected = event.target.selectedOptions[0];
    if (selected.dataset.medicine) {
        const medicine = JSON.parse(selected.dataset.medicine);
        fillMedicine(medicine);
        showMedicine(medicine);
    } else {
        document.getElementById('medicine_id').value = '';
    }
});
// Editing the prescribed identity deliberately switches to manual-name matching.
for (const key of ['medicine_name', 'medicine_type']) {
    document.getElementById(key)?.addEventListener('input', () => {
        const id = document.getElementById('medicine_id');
        if (id) id.value = '';
        const select = document.getElementById('registeredMedicine');
        if (select) select.value = '';
    });
}
