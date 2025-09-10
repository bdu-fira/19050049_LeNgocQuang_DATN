from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_socketio import SocketIO, emit
from datetime import datetime, timedelta, timezone
import json
import math
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from database_config import database_service

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data['id']
        self.username = user_data['username']
        self.email = user_data['email']
        self.password_hash = user_data['password_hash']
        self.role = user_data.get('role', 'doctor')
        self.created_at = user_data.get('created_at')

@login_manager.user_loader
def load_user(user_id):
    user_data = database_service.get_user_by_id(int(user_id))
    if user_data:
        return User(user_data)
    return None

# Helper function to detect falls based on Run MHsensor series
def detect_fall_from_sensor(fall_signal):
    """
    Process fall detection signal from Run MHsensor series
    Returns (fall_detected: bool, confidence: float)
    """
    try:
        if fall_signal:
            return True, 0.9  # High confidence for digital fall sensor
        return False, 0.0
    except (TypeError, ValueError):
        return False, 0.0

# Helper function to determine room based on GPS coordinates
def determine_room_from_gps(latitude, longitude):
    """
    Determine room location based on GPS coordinates from NEO-6M
    This is a simplified example - in reality you'd have a mapping of GPS to rooms
    """
    # Example hospital room coordinates (simplified)
    rooms = {
        'Phòng 101': {'lat_min': 10.7756, 'lat_max': 10.7757, 'lng_min': 106.7017, 'lng_max': 106.7018},
        'Phòng 102': {'lat_min': 10.7757, 'lat_max': 10.7758, 'lng_min': 106.7017, 'lng_max': 106.7018},
        'Phòng 103': {'lat_min': 10.7758, 'lat_max': 10.7759, 'lng_min': 106.7017, 'lng_max': 106.7018},
        'Phòng Cấp Cứu': {'lat_min': 10.7759, 'lat_max': 10.7760, 'lng_min': 106.7017, 'lng_max': 106.7018},
        'ICU': {'lat_min': 10.7760, 'lat_max': 10.7761, 'lng_min': 106.7017, 'lng_max': 106.7018},
    }
    
    for room_name, coords in rooms.items():
        if (coords['lat_min'] <= latitude <= coords['lat_max'] and 
            coords['lng_min'] <= longitude <= coords['lng_max']):
            return room_name, 0.9  # High confidence for exact match
    
    return 'Phòng Không Xác Định', 0.1  # Low confidence if no match

# Routes
@app.route('/')
@login_required
def dashboard():
    patients = database_service.get_all_patients()
    recent_alerts = database_service.get_unacknowledged_alerts(10)
    return render_template('dashboard.html', patients=patients, alerts=recent_alerts)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_data = database_service.get_user_by_username(username)
        
        if user_data and check_password_hash(user_data['password_hash'], password):
            user = User(user_data)
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/patients')
@login_required
def patients():
    patients = database_service.get_all_patients()
    return render_template('patients.html', patients=patients)

@app.route('/patient/<patient_id>')
@login_required
def patient_detail(patient_id):
    patient = database_service.get_patient_by_id(int(patient_id))
    if not patient:
        return "Patient not found", 404
    
    recent_readings = database_service.get_patient_readings(int(patient_id), hours=24)
    return render_template('patient_detail.html', patient=patient, readings=recent_readings)

@app.route('/add_patient', methods=['GET', 'POST'])
@login_required
def add_patient():
    if request.method == 'POST':
        # Get device ID from the selected device
        device_id = request.form['device_id']
        
        # Find the device to get its internal ID
        device = database_service.get_device_by_device_id(device_id)
        if not device:
            flash('Thiết bị ESP32 không tồn tại', 'error')
            return redirect(url_for('add_patient'))
        
        patient_data = {
            'name': request.form['name'],
            'age': int(request.form['age']),
            'gender': request.form['gender'],
            'phone': request.form['phone'],
            'email': request.form['email'],
            'medical_id': request.form['medical_id'],
            'room_number': request.form['room_number'],
            'esp32_device_id': device['id'],  # Use internal device ID
            'status': 'active'
        }
        database_service.create_patient(patient_data)
        return redirect(url_for('patients'))
    
    # Get available ESP32 devices for selection
    devices = database_service.get_active_devices()
    return render_template('add_patient.html', devices=devices)

# ESP32 Device Management Routes
@app.route('/devices')
@login_required
def devices():
    devices = database_service.get_all_devices()
    return render_template('devices.html', devices=devices)

@app.route('/add_device', methods=['GET', 'POST'])
@login_required
def add_device():
    if request.method == 'POST':
        device_data = {
            'device_id': request.form['device_id'],
            'device_name': request.form['device_name'],
            'device_type': request.form['device_type'],
            'firmware_version': request.form.get('firmware_version'),
            'ip_address': request.form.get('ip_address'),
            'mac_address': request.form.get('mac_address'),
            'room_location': request.form.get('room_location'),
            'is_active': True,
            'battery_level': 100.0,
            'signal_strength': -50
        }
        database_service.create_device(device_data)
        return redirect(url_for('devices'))
    
    return render_template('add_device.html')

@app.route('/edit_device/<device_id>', methods=['GET', 'POST'])
@login_required
def edit_device(device_id):
    device = database_service.get_device_by_id(device_id)
    if not device:
        return "Device not found", 404
    
    if request.method == 'POST':
        update_data = {
            'device_name': request.form['device_name'],
            'device_type': request.form['device_type'],
            'firmware_version': request.form.get('firmware_version'),
            'ip_address': request.form.get('ip_address'),
            'mac_address': request.form.get('mac_address'),
            'room_location': request.form.get('room_location'),
            'is_active': 'is_active' in request.form
        }
        database_service.update_device(device_id, update_data)
        return redirect(url_for('devices'))
    
    return render_template('edit_device.html', device=device)

@app.route('/api/delete_device/<device_id>', methods=['DELETE'])
@login_required
def delete_device(device_id):
    # Check if device is assigned to any patients
    patients = database_service.get_all_patients()
    assigned_patients = [p for p in patients if p.get('device_id') == device_id]
    
    if assigned_patients:
        return jsonify({'error': 'Cannot delete device. It is assigned to patients.'}), 400
    
    database_service.delete_device(device_id)
    return jsonify({'success': True})

# API Endpoints for ESP32 - Updated for real sensors
@app.route('/api/sensor_data', methods=['POST'])
def receive_sensor_data():
    try:
        data = request.json
        device_id = data.get('device_id')
        
        # Find patient by ESP32 device ID
        patient = database_service.get_patient_by_device_id(device_id)
        if not patient:
            return jsonify({'error': 'Patient not found for device ID'}), 404
        
        # Update device last seen
        database_service.update_device(device_id, {
            'last_seen': datetime.now(timezone.utc),
            'battery_level': data.get('battery_level', 100),
            'signal_strength': data.get('signal_strength', -50)
        })
        
        # Process fall detection from Run MHsensor series
        fall_detected = False
        fall_confidence = 0.0
        if 'fall_detected' in data:
            fall_detected, fall_confidence = detect_fall_from_sensor(data['fall_detected'])
        
        # Process GPS location from NEO-6M
        room_detected = 'Unknown'
        location_confidence = 0.0
        if 'gps_lat' in data and 'gps_lng' in data:
            room_detected, location_confidence = determine_room_from_gps(
                data['gps_lat'], data['gps_lng']
            )
        
        # Create comprehensive sensor reading with all real sensor data
        reading_data = {
            'patient_id': patient['id'],
            'device_id': device_id,
            
            # Vital signs from MH-ETLive
            'heart_rate': data.get('heart_rate'),  # From MH-ETLive
            'oxygen_saturation': data.get('oxygen_saturation'),  # From MH-ETLive
            'blood_pressure_systolic': data.get('bp_systolic'),
            'blood_pressure_diastolic': data.get('bp_diastolic'),
            'respiratory_rate': data.get('respiratory_rate'),
            
            # Body temperature from DS18B20
            'body_temperature': data.get('body_temperature'),  # From DS18B20
            
            # Room environment from DHT11
            'room_temperature': data.get('room_temperature'),  # From DHT11
            'humidity': data.get('humidity'),  # From DHT11
            
            # ECG data from AD8232
            'ecg_value': data.get('ecg_value'),  # From AD8232
            'ecg_leads_connected': data.get('ecg_leads_connected', False),
            'ecg_status': data.get('ecg_status', 'Normal'),
            'ecg_data': data.get('ecg_data'),  # ECG data buffer
            
            # Fall detection from Run MHsensor series
            'fall_detected': fall_detected,
            'fall_confidence': fall_confidence,
            
            # GPS location from NEO-6M
            'gps_latitude': data.get('gps_lat'),
            'gps_longitude': data.get('gps_lng'),
            'gps_accuracy': data.get('gps_accuracy'),
            'room_detected': room_detected,
            'location_confidence': location_confidence,
            
            # Emergency button
            'emergency_button_pressed': data.get('emergency_button_pressed', False),
            
            # Device status
            'battery_level': data.get('battery_level'),
            'signal_strength': data.get('signal_strength')
        }
        
        # Check for critical values and set alerts based on real sensor data
        alert_level = 'normal'
        is_emergency = False
        alert_messages = []
        
        # Heart rate checks (from MH-ETLive)
        if reading_data['heart_rate']:
            hr = reading_data['heart_rate']
            if hr < 60 or hr > 100:
                alert_level = 'warning'
                alert_messages.append(f"Nhịp tim: {hr} bpm")
            if hr < 40 or hr > 120:
                alert_level = 'critical'
                is_emergency = True
        
        # Body temperature checks (from DS18B20)
        if reading_data['body_temperature']:
            temp = reading_data['body_temperature']
            if temp < 36 or temp > 38:
                alert_level = 'warning'
                alert_messages.append(f"Nhiệt độ cơ thể: {temp}°C")
            if temp < 35 or temp > 39:
                alert_level = 'critical'
                is_emergency = True
        
        # Oxygen saturation checks (from MH-ETLive)
        if reading_data['oxygen_saturation']:
            spo2 = reading_data['oxygen_saturation']
            if spo2 < 95:
                alert_level = 'warning'
                alert_messages.append(f"Độ bão hòa oxy: {spo2}%")
            if spo2 < 90:
                alert_level = 'critical'
                is_emergency = True
        
        # Room environment checks (from DHT11)
        if reading_data['room_temperature']:
            room_temp = reading_data['room_temperature']
            if room_temp < 18 or room_temp > 30:
                alert_level = 'warning'
                alert_messages.append(f"Nhiệt độ phòng: {room_temp}°C")
        
        if reading_data['humidity']:
            room_hum = reading_data['humidity']
            if room_hum < 30 or room_hum > 70:
                alert_level = 'warning'
                alert_messages.append(f"Độ ẩm phòng: {room_hum}%")
        
        # ECG checks (from AD8232)
        if reading_data['ecg_leads_connected'] and not reading_data['ecg_value']:
            alert_level = 'warning'
            alert_messages.append("Điện cực ECG bị ngắt kết nối")
        
        # Fall detection alert (from Run MHsensor series)
        if fall_detected:
            alert_level = 'critical'
            is_emergency = True
            alert_messages.append(f"Phát hiện té ngã (độ tin cậy: {fall_confidence:.1%})")
        
        # Emergency button alert
        if reading_data['emergency_button_pressed']:
            alert_level = 'critical'
            is_emergency = True
            alert_messages.append("Nút cảnh báo khẩn cấp được nhấn")
        
        reading_data['alert_level'] = alert_level
        reading_data['is_emergency'] = is_emergency
        
        # Save sensor reading
        database_service.create_sensor_reading(reading_data)
        
        # Create alert if necessary
        if alert_level != 'normal':
            alert_message = f"Bệnh nhân {patient['name']} cảnh báo: " + "; ".join(alert_messages)
            
            alert_data = {
                'patient_id': patient['id'],
                'alert_type': 'fall_detection' if fall_detected else 'vital_signs',
                'message': alert_message,
                'severity': alert_level,
                'is_acknowledged': False
            }
            database_service.create_alert(alert_data)
        
        # Emit comprehensive real-time update to connected clients
        socketio.emit('sensor_update', {
            'patient_id': patient['id'],
            'patient_name': patient['name'],
            'reading': {
                # Vital signs
                'heart_rate': reading_data['heart_rate'],
                'body_temperature': reading_data['body_temperature'],
                'oxygen_saturation': reading_data['oxygen_saturation'],
                'blood_pressure': f"{reading_data['blood_pressure_systolic']}/{reading_data['blood_pressure_diastolic']}" if reading_data['blood_pressure_systolic'] else None,
                'respiratory_rate': reading_data['respiratory_rate'],
                
                # Room environment
                'room_temperature': reading_data['room_temperature'],
                'humidity': reading_data['humidity'],
                
                # ECG data
                'ecg_value': reading_data['ecg_value'],
                'ecg_leads_connected': reading_data['ecg_leads_connected'],
                'ecg_status': reading_data['ecg_status'],
                
                # Fall detection
                'fall_detected': fall_detected,
                'fall_confidence': fall_confidence,
                
                # GPS location
                'gps_latitude': reading_data['gps_latitude'],
                'gps_longitude': reading_data['gps_longitude'],
                'room_detected': room_detected,
                
                # Emergency
                'emergency_button_pressed': reading_data['emergency_button_pressed'],
                'alert_level': alert_level,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        })
        
        return jsonify({
            'status': 'success', 
            'alert_level': alert_level, 
            'fall_detected': fall_detected,
            'room_detected': room_detected
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/patient_status/<device_id>')
def get_patient_status(device_id):
    patient = database_service.get_patient_by_device_id(device_id)
    if not patient:
        return jsonify({'error': 'Patient not found'}), 404
    
    latest_reading = database_service.get_latest_reading(patient['id'])
    
    return jsonify({
        'patient_id': patient['id'],
        'name': patient['name'],
        'status': patient['status'],
        'latest_reading': {
            'heart_rate': latest_reading.get('heart_rate') if latest_reading else None,
            'body_temperature': latest_reading.get('body_temperature') if latest_reading else None,
            'oxygen_saturation': latest_reading.get('oxygen_saturation') if latest_reading else None,
            'room_temperature': latest_reading.get('room_temperature') if latest_reading else None,
            'humidity': latest_reading.get('humidity') if latest_reading else None,
            'fall_detected': latest_reading.get('fall_detected', False),
            'room_detected': latest_reading.get('room_detected', 'Unknown'),
            'alert_level': latest_reading.get('alert_level', 'normal'),
            'timestamp': latest_reading.get('timestamp') if latest_reading else None
        }
    })

# WebSocket events
@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

# Additional API endpoints
@app.route('/api/patients_status')
def get_patients_status():
    patients = database_service.get_all_patients()
    result = []
    
    for patient in patients:
        latest_reading = database_service.get_latest_reading(patient['id'])
        
        patient_data = {
            'id': patient['id'],
            'name': patient['name'],
            'status': patient['status'],
            'latest_reading': None
        }
        
        if latest_reading:
            patient_data['latest_reading'] = {
                'heart_rate': latest_reading.get('heart_rate'),
                'body_temperature': latest_reading.get('body_temperature'),
                'oxygen_saturation': latest_reading.get('oxygen_saturation'),
                'room_temperature': latest_reading.get('room_temperature'),
                'humidity': latest_reading.get('humidity'),
                'fall_detected': latest_reading.get('fall_detected', False),
                'room_detected': latest_reading.get('room_detected', 'Unknown'),
                'alert_level': latest_reading.get('alert_level', 'normal'),
                'timestamp': latest_reading.get('timestamp')
            }
        
        result.append(patient_data)
    
    return jsonify(result)

@app.route('/api/patient_readings/<patient_id>')
def get_patient_readings(patient_id):
    hours = request.args.get('hours', 24, type=int)
    readings = database_service.get_patient_readings(int(patient_id), hours)
    
    result = []
    for reading in readings:
        result.append({
            'timestamp': reading.get('timestamp'),
            'heart_rate': reading.get('heart_rate'),
            'body_temperature': reading.get('body_temperature'),
            'oxygen_saturation': reading.get('oxygen_saturation'),
            'blood_pressure_systolic': reading.get('blood_pressure_systolic'),
            'blood_pressure_diastolic': reading.get('blood_pressure_diastolic'),
            'respiratory_rate': reading.get('respiratory_rate'),
            'room_temperature': reading.get('room_temperature'),
            'humidity': reading.get('humidity'),
            'ecg_value': reading.get('ecg_value'),
            'ecg_status': reading.get('ecg_status'),
            'fall_detected': reading.get('fall_detected', False),
            'room_detected': reading.get('room_detected', 'Unknown'),
            'gps_latitude': reading.get('gps_latitude'),
            'gps_longitude': reading.get('gps_longitude'),
            'alert_level': reading.get('alert_level', 'normal')
        })
    
    return jsonify(result)

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now(timezone.utc).isoformat()})

@app.route('/api/acknowledge_alert/<alert_id>', methods=['POST'])
@login_required
def acknowledge_alert(alert_id):
    database_service.acknowledge_alert(int(alert_id), current_user.id)
    return jsonify({'success': True})

@app.route('/api/delete_patient/<patient_id>', methods=['DELETE'])
@login_required
def delete_patient(patient_id):
    database_service.delete_patient(int(patient_id))
    return jsonify({'success': True})

# Initialize database and create default admin user
def create_default_admin():
    """Create default admin user if not exists"""
    admin_user = database_service.get_user_by_username('admin')
    if not admin_user:
        admin_data = {
            'username': 'admin',
            'email': 'admin@hospital.com',
            'password_hash': generate_password_hash('admin123'),
            'role': 'admin'
        }
        database_service.create_user(admin_data)
        print("Created default admin user: admin/admin123")

if __name__ == '__main__':
    # Initialize default admin user
    create_default_admin()
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)