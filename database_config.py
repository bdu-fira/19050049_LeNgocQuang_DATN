import os
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import json

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://patient_user:patient_password@postgres:5432/patient_monitor')

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()

# Database Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default='doctor')  # doctor, admin, nurse
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    patients = relationship("Patient", back_populates="assigned_doctor")
    alerts_acknowledged = relationship("Alert", back_populates="acknowledged_by")

class ESP32Device(Base):
    __tablename__ = "esp32_devices"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    device_type = Column(String(50), default='patient_monitor')
    location = Column(String(100))
    firmware_version = Column(String(50))
    ip_address = Column(String(45))
    mac_address = Column(String(17))
    battery_level = Column(Float, default=100.0)
    signal_strength = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    last_seen = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    patient = relationship("Patient", back_populates="device", uselist=False)
    sensor_readings = relationship("SensorReading", back_populates="device")

class Patient(Base):
    __tablename__ = "patients"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    age = Column(Integer)
    gender = Column(String(10))
    phone = Column(String(20))                    # Số điện thoại liên lạc
    email = Column(String(100))                   # Email liên lạc
    medical_id = Column(String(50), unique=True)  # Mã bệnh nhân duy nhất
    room_number = Column(String(20))
    bed_number = Column(String(10))
    admission_date = Column(DateTime, default=datetime.utcnow)
    diagnosis = Column(Text)
    assigned_doctor_id = Column(Integer, ForeignKey("users.id"))
    device_id = Column(Integer, ForeignKey("esp32_devices.id"), unique=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    assigned_doctor = relationship("User", back_populates="patients")
    device = relationship("ESP32Device", back_populates="patient")
    sensor_readings = relationship("SensorReading", back_populates="patient")
    alerts = relationship("Alert", back_populates="patient")

class SensorReading(Base):
    __tablename__ = "sensor_readings"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    device_id = Column(Integer, ForeignKey("esp32_devices.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Vital signs from MH-ETLive
    heart_rate = Column(Float)                    # Nhịp tim từ MH-ETLive
    oxygen_saturation = Column(Float)             # Độ bão hòa oxy từ MH-ETLive
    blood_pressure_systolic = Column(Float)       # Huyết áp tâm thu
    blood_pressure_diastolic = Column(Float)      # Huyết áp tâm trương
    respiratory_rate = Column(Float)              # Nhịp thở
    
    # Body temperature from DS18B20
    body_temperature = Column(Float)              # Nhiệt độ cơ thể từ DS18B20
    
    # Room environment from DHT11
    room_temperature = Column(Float)              # Nhiệt độ phòng từ DHT11
    humidity = Column(Float)                      # Độ ẩm phòng từ DHT11
    
    # ECG data from AD8232
    ecg_value = Column(Float)                     # Giá trị điện tâm đồ từ AD8232
    ecg_leads_connected = Column(Boolean, default=False)  # Trạng thái kết nối điện cực
    ecg_status = Column(String(20), default='Normal')     # Trạng thái ECG
    ecg_data = Column(Text)                       # ECG data buffer cho phân tích
    
    # Fall detection from Run MHsensor series
    fall_detected = Column(Boolean, default=False)         # Phát hiện té ngã
    fall_confidence = Column(Float, default=0.0)           # Độ tin cậy phát hiện té ngã
    
    # GPS location from NEO-6M
    gps_latitude = Column(Float)                  # Vĩ độ GPS
    gps_longitude = Column(Float)                 # Kinh độ GPS
    gps_accuracy = Column(Float)                  # Độ chính xác GPS
    room_detected = Column(String(50))            # Phòng được xác định từ GPS
    location_confidence = Column(Float, default=0.0)       # Độ tin cậy vị trí
    
    # Emergency button
    emergency_button_pressed = Column(Boolean, default=False)  # Nút cảnh báo khẩn cấp
    
    # Device status
    battery_level = Column(Float)                 # Mức pin thiết bị
    signal_strength = Column(Integer)             # Cường độ tín hiệu WiFi
    
    # Alert level
    alert_level = Column(String(20), default='normal')  # normal, warning, critical
    is_emergency = Column(Boolean, default=False)       # Có phải tình huống khẩn cấp
    
    # Relationships
    patient = relationship("Patient", back_populates="sensor_readings")
    device = relationship("ESP32Device", back_populates="sensor_readings")

class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    device_id = Column(Integer, ForeignKey("esp32_devices.id"), nullable=False)
    alert_type = Column(String(50), nullable=False)  # vital_signs, fall_detection, device_offline, ecg_irregular, emergency_button, gps_location
    severity = Column(String(20), nullable=False)  # normal, warning, critical
    message = Column(Text, nullable=False)
    is_acknowledged = Column(Boolean, default=False)
    acknowledged_by_id = Column(Integer, ForeignKey("users.id"))
    acknowledged_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    patient = relationship("Patient", back_populates="alerts")
    device = relationship("ESP32Device")
    acknowledged_by = relationship("User", back_populates="alerts_acknowledged")

# Database service class
class DatabaseService:
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal
        self.create_tables()
    
    def create_tables(self):
        """Create all database tables"""
        Base.metadata.create_all(bind=self.engine)
    
    def get_db(self):
        """Get database session"""
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    # User operations
    def create_user(self, user_data):
        db = self.SessionLocal()
        try:
            user = User(
                username=user_data['username'],
                email=user_data['email'],
                password_hash=user_data['password_hash'],
                role=user_data.get('role', 'doctor')
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return user.id
        finally:
            db.close()
    
    def get_user_by_username(self, username):
        db = self.SessionLocal()
        try:
            user = db.query(User).filter(User.username == username).first()
            if user:
                return {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'password_hash': user.password_hash,
                    'role': user.role,
                    'created_at': user.created_at
                }
            return None
        finally:
            db.close()
    
    def get_user_by_id(self, user_id):
        db = self.SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                return {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'password_hash': user.password_hash,
                    'role': user.role,
                    'created_at': user.created_at
                }
            return None
        finally:
            db.close()
    
    # ESP32 Device operations
    def create_device(self, device_data):
        db = self.SessionLocal()
        try:
            device = ESP32Device(
                device_id=device_data['device_id'],
                name=device_data['device_name'],
                device_type=device_data.get('device_type', 'patient_monitor'),
                location=device_data.get('room_location'),
                firmware_version=device_data.get('firmware_version'),
                ip_address=device_data.get('ip_address'),
                mac_address=device_data.get('mac_address'),
                battery_level=device_data.get('battery_level', 100.0),
                signal_strength=device_data.get('signal_strength', -50),
                is_active=device_data.get('is_active', True)
            )
            db.add(device)
            db.commit()
            db.refresh(device)
            return device.id
        finally:
            db.close()
    
    def get_device_by_id(self, device_id):
        db = self.SessionLocal()
        try:
            device = db.query(ESP32Device).filter(ESP32Device.id == device_id).first()
            if device:
                return {
                    'id': device.id,
                    'device_id': device.device_id,
                    'device_name': device.name,
                    'device_type': device.device_type,
                    'room_location': device.location,
                    'firmware_version': device.firmware_version,
                    'ip_address': device.ip_address,
                    'mac_address': device.mac_address,
                    'battery_level': device.battery_level,
                    'signal_strength': device.signal_strength,
                    'is_active': device.is_active,
                    'last_seen': device.last_seen,
                    'created_at': device.created_at
                }
            return None
        finally:
            db.close()
    
    def get_device_by_device_id(self, device_id):
        db = self.SessionLocal()
        try:
            device = db.query(ESP32Device).filter(ESP32Device.device_id == device_id).first()
            if device:
                return {
                    'id': device.id,
                    'device_id': device.device_id,
                    'device_name': device.name,
                    'device_type': device.device_type,
                    'room_location': device.location,
                    'firmware_version': device.firmware_version,
                    'ip_address': device.ip_address,
                    'mac_address': device.mac_address,
                    'battery_level': device.battery_level,
                    'signal_strength': device.signal_strength,
                    'is_active': device.is_active,
                    'last_seen': device.last_seen,
                    'created_at': device.created_at
                }
            return None
        finally:
            db.close()
    
    def get_all_devices(self):
        db = self.SessionLocal()
        try:
            devices = db.query(ESP32Device).all()
            result = []
            for device in devices:
                result.append({
                    'id': device.id,
                    'device_id': device.device_id,
                    'device_name': device.name,
                    'device_type': device.device_type,
                    'room_location': device.location,
                    'firmware_version': device.firmware_version,
                    'ip_address': device.ip_address,
                    'mac_address': device.mac_address,
                    'battery_level': device.battery_level,
                    'signal_strength': device.signal_strength,
                    'is_active': device.is_active,
                    'last_seen': device.last_seen,
                    'created_at': device.created_at
                })
            return result
        finally:
            db.close()
    
    def get_active_devices(self):
        db = self.SessionLocal()
        try:
            devices = db.query(ESP32Device).filter(ESP32Device.is_active == True).all()
            result = []
            for device in devices:
                result.append({
                    'id': device.id,
                    'device_id': device.device_id,
                    'device_name': device.name,
                    'device_type': device.device_type,
                    'room_location': device.location,
                    'firmware_version': device.firmware_version,
                    'ip_address': device.ip_address,
                    'mac_address': device.mac_address,
                    'battery_level': device.battery_level,
                    'signal_strength': device.signal_strength,
                    'is_active': device.is_active,
                    'last_seen': device.last_seen,
                    'created_at': device.created_at
                })
            return result
        finally:
            db.close()
    
    def update_device(self, device_id, update_data):
        db = self.SessionLocal()
        try:
            device = db.query(ESP32Device).filter(ESP32Device.id == device_id).first()
            if device:
                for key, value in update_data.items():
                    if hasattr(device, key):
                        setattr(device, key, value)
                db.commit()
                return True
            return False
        finally:
            db.close()
    
    def delete_device(self, device_id):
        db = self.SessionLocal()
        try:
            device = db.query(ESP32Device).filter(ESP32Device.id == device_id).first()
            if device:
                db.delete(device)
                db.commit()
                return True
            return False
        finally:
            db.close()
    
    # Patient operations
    def create_patient(self, patient_data):
        db = self.SessionLocal()
        try:
            patient = Patient(
                name=patient_data['name'],
                age=patient_data.get('age'),
                gender=patient_data.get('gender'),
                phone=patient_data.get('phone'),
                email=patient_data.get('email'),
                medical_id=patient_data.get('medical_id'),
                room_number=patient_data.get('room_number'),
                bed_number=patient_data.get('bed_number'),
                diagnosis=patient_data.get('diagnosis'),
                assigned_doctor_id=patient_data.get('assigned_doctor_id'),
                device_id=patient_data.get('esp32_device_id'),
                is_active=patient_data.get('is_active', True)
            )
            db.add(patient)
            db.commit()
            db.refresh(patient)
            return patient.id
        finally:
            db.close()
    
    def get_patient_by_id(self, patient_id):
        db = self.SessionLocal()
        try:
            patient = db.query(Patient).filter(Patient.id == patient_id).first()
            if patient:
                return {
                    'id': patient.id,
                    'name': patient.name,
                    'age': patient.age,
                    'gender': patient.gender,
                    'phone': patient.phone,
                    'email': patient.email,
                    'medical_id': patient.medical_id,
                    'room_number': patient.room_number,
                    'bed_number': patient.bed_number,
                    'admission_date': patient.admission_date,
                    'diagnosis': patient.diagnosis,
                    'assigned_doctor_id': patient.assigned_doctor_id,
                    'device_id': patient.device_id,
                    'is_active': patient.is_active,
                    'created_at': patient.created_at
                }
            return None
        finally:
            db.close()
    
    def get_patient_by_device_id(self, device_id):
        db = self.SessionLocal()
        try:
            device = db.query(ESP32Device).filter(ESP32Device.device_id == device_id).first()
            if device and device.patient:
                patient = device.patient
                return {
                    'id': patient.id,
                    'name': patient.name,
                    'age': patient.age,
                    'gender': patient.gender,
                    'phone': patient.phone,
                    'email': patient.email,
                    'medical_id': patient.medical_id,
                    'room_number': patient.room_number,
                    'bed_number': patient.bed_number,
                    'admission_date': patient.admission_date,
                    'diagnosis': patient.diagnosis,
                    'assigned_doctor_id': patient.assigned_doctor_id,
                    'device_id': patient.device_id,
                    'is_active': patient.is_active,
                    'created_at': patient.created_at
                }
            return None
        finally:
            db.close()
    
    def get_all_patients(self):
        db = self.SessionLocal()
        try:
            patients = db.query(Patient).filter(Patient.is_active == True).all()
            result = []
            for patient in patients:
                result.append({
                    'id': patient.id,
                    'name': patient.name,
                    'age': patient.age,
                    'gender': patient.gender,
                    'phone': patient.phone,
                    'email': patient.email,
                    'medical_id': patient.medical_id,
                    'room_number': patient.room_number,
                    'bed_number': patient.bed_number,
                    'admission_date': patient.admission_date,
                    'diagnosis': patient.diagnosis,
                    'assigned_doctor_id': patient.assigned_doctor_id,
                    'device_id': patient.device_id,
                    'is_active': patient.is_active,
                    'created_at': patient.created_at
                })
            return result
        finally:
            db.close()
    
    def update_patient(self, patient_id, update_data):
        db = self.SessionLocal()
        try:
            patient = db.query(Patient).filter(Patient.id == patient_id).first()
            if patient:
                for key, value in update_data.items():
                    if hasattr(patient, key):
                        setattr(patient, key, value)
                db.commit()
                return True
            return False
        finally:
            db.close()
    
    def delete_patient(self, patient_id):
        db = self.SessionLocal()
        try:
            patient = db.query(Patient).filter(Patient.id == patient_id).first()
            if patient:
                db.delete(patient)
                db.commit()
                return True
            return False
        finally:
            db.close()
    
    # Sensor Reading operations
    def create_sensor_reading(self, reading_data):
        db = self.SessionLocal()
        try:
            reading = SensorReading(
                patient_id=reading_data['patient_id'],
                device_id=reading_data['device_id'],
                heart_rate=reading_data.get('heart_rate'),
                oxygen_saturation=reading_data.get('oxygen_saturation'),
                blood_pressure_systolic=reading_data.get('blood_pressure_systolic'),
                blood_pressure_diastolic=reading_data.get('blood_pressure_diastolic'),
                respiratory_rate=reading_data.get('respiratory_rate'),
                body_temperature=reading_data.get('body_temperature'),
                room_temperature=reading_data.get('room_temperature'),
                humidity=reading_data.get('humidity'),
                ecg_value=reading_data.get('ecg_value'),
                ecg_leads_connected=reading_data.get('ecg_leads_connected', False),
                ecg_status=reading_data.get('ecg_status', 'Normal'),
                ecg_data=reading_data.get('ecg_data'),
                fall_detected=reading_data.get('fall_detected', False),
                fall_confidence=reading_data.get('fall_confidence', 0.0),
                gps_latitude=reading_data.get('gps_latitude'),
                gps_longitude=reading_data.get('gps_longitude'),
                gps_accuracy=reading_data.get('gps_accuracy'),
                room_detected=reading_data.get('room_detected'),
                location_confidence=reading_data.get('location_confidence', 0.0),
                emergency_button_pressed=reading_data.get('emergency_button_pressed', False),
                battery_level=reading_data.get('battery_level'),
                signal_strength=reading_data.get('signal_strength'),
                alert_level=reading_data.get('alert_level', 'normal'),
                is_emergency=reading_data.get('is_emergency', False)
            )
            db.add(reading)
            db.commit()
            db.refresh(reading)
            return reading.id
        finally:
            db.close()
    
    def get_latest_reading(self, patient_id):
        db = self.SessionLocal()
        try:
            reading = db.query(SensorReading).filter(
                SensorReading.patient_id == patient_id
            ).order_by(SensorReading.timestamp.desc()).first()
            
            if reading:
                return {
                    'id': reading.id,
                    'patient_id': reading.patient_id,
                    'device_id': reading.device_id,
                    'timestamp': reading.timestamp,
                    'heart_rate': reading.heart_rate,
                    'oxygen_saturation': reading.oxygen_saturation,
                    'blood_pressure_systolic': reading.blood_pressure_systolic,
                    'blood_pressure_diastolic': reading.blood_pressure_diastolic,
                    'respiratory_rate': reading.respiratory_rate,
                    'body_temperature': reading.body_temperature,
                    'room_temperature': reading.room_temperature,
                    'humidity': reading.humidity,
                    'ecg_value': reading.ecg_value,
                    'ecg_leads_connected': reading.ecg_leads_connected,
                    'ecg_status': reading.ecg_status,
                    'ecg_data': reading.ecg_data,
                    'fall_detected': reading.fall_detected,
                    'fall_confidence': reading.fall_confidence,
                    'gps_latitude': reading.gps_latitude,
                    'gps_longitude': reading.gps_longitude,
                    'gps_accuracy': reading.gps_accuracy,
                    'room_detected': reading.room_detected,
                    'location_confidence': reading.location_confidence,
                    'emergency_button_pressed': reading.emergency_button_pressed,
                    'battery_level': reading.battery_level,
                    'signal_strength': reading.signal_strength,
                    'alert_level': reading.alert_level,
                    'is_emergency': reading.is_emergency
                }
            return None
        finally:
            db.close()
    
    def get_patient_readings(self, patient_id, hours=24):
        db = self.SessionLocal()
        try:
            from datetime import datetime, timedelta
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            readings = db.query(SensorReading).filter(
                SensorReading.patient_id == patient_id,
                SensorReading.timestamp >= cutoff_time
            ).order_by(SensorReading.timestamp.desc()).all()
            
            result = []
            for reading in readings:
                result.append({
                    'id': reading.id,
                    'patient_id': reading.patient_id,
                    'device_id': reading.device_id,
                    'timestamp': reading.timestamp,
                    'heart_rate': reading.heart_rate,
                    'oxygen_saturation': reading.oxygen_saturation,
                    'blood_pressure_systolic': reading.blood_pressure_systolic,
                    'blood_pressure_diastolic': reading.blood_pressure_diastolic,
                    'respiratory_rate': reading.respiratory_rate,
                    'body_temperature': reading.body_temperature,
                    'room_temperature': reading.room_temperature,
                    'humidity': reading.humidity,
                    'ecg_value': reading.ecg_value,
                    'ecg_leads_connected': reading.ecg_leads_connected,
                    'ecg_status': reading.ecg_status,
                    'ecg_data': reading.ecg_data,
                    'fall_detected': reading.fall_detected,
                    'fall_confidence': reading.fall_confidence,
                    'gps_latitude': reading.gps_latitude,
                    'gps_longitude': reading.gps_longitude,
                    'gps_accuracy': reading.gps_accuracy,
                    'room_detected': reading.room_detected,
                    'location_confidence': reading.location_confidence,
                    'emergency_button_pressed': reading.emergency_button_pressed,
                    'battery_level': reading.battery_level,
                    'signal_strength': reading.signal_strength,
                    'alert_level': reading.alert_level,
                    'is_emergency': reading.is_emergency
                })
            return result
        finally:
            db.close()
    
    # Alert operations
    def create_alert(self, alert_data):
        db = self.SessionLocal()
        try:
            alert = Alert(
                patient_id=alert_data['patient_id'],
                device_id=alert_data['device_id'],
                alert_type=alert_data['alert_type'],
                severity=alert_data['severity'],
                message=alert_data['message'],
                is_acknowledged=alert_data.get('is_acknowledged', False)
            )
            db.add(alert)
            db.commit()
            db.refresh(alert)
            return alert.id
        finally:
            db.close()
    
    def get_unacknowledged_alerts(self, limit=10):
        db = self.SessionLocal()
        try:
            alerts = db.query(Alert).filter(
                Alert.is_acknowledged == False
            ).order_by(Alert.created_at.desc()).limit(limit).all()
            
            result = []
            for alert in alerts:
                result.append({
                    'id': alert.id,
                    'patient_id': alert.patient_id,
                    'device_id': alert.device_id,
                    'alert_type': alert.alert_type,
                    'severity': alert.severity,
                    'message': alert.message,
                    'is_acknowledged': alert.is_acknowledged,
                    'acknowledged_by_id': alert.acknowledged_by_id,
                    'acknowledged_at': alert.acknowledged_at,
                    'created_at': alert.created_at
                })
            return result
        finally:
            db.close()
    
    def acknowledge_alert(self, alert_id, user_id):
        db = self.SessionLocal()
        try:
            alert = db.query(Alert).filter(Alert.id == alert_id).first()
            if alert:
                alert.is_acknowledged = True
                alert.acknowledged_by_id = user_id
                alert.acknowledged_at = datetime.utcnow()
                db.commit()
                return True
            return False
        finally:
            db.close()

# Create global database service instance
database_service = DatabaseService() 