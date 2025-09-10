#!/usr/bin/env python3
"""
Database Migration Script for Patient Monitor
Adds new columns to patients table: phone, email, medical_id
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Database connection for migration (from host machine)
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://patient_user:patient_password@localhost:5432/patient_monitor')

def update_database():
    """Update database schema to add new columns"""
    
    print("🔄 Starting database migration...")
    
    # Create engine
    engine = create_engine(DATABASE_URL)
    
    try:
        with engine.connect() as connection:
            print("✅ Connected to database successfully")
            
            # Check if columns already exist
            check_query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'patients' 
            AND column_name IN ('phone', 'email', 'medical_id')
            """
            
            result = connection.execute(text(check_query))
            existing_columns = [row[0] for row in result]
            
            print(f"📋 Existing columns: {existing_columns}")
            
            # Add missing columns
            migrations = []
            
            if 'phone' not in existing_columns:
                migrations.append("ADD COLUMN phone VARCHAR(20)")
                print("➕ Will add phone column")
            
            if 'email' not in existing_columns:
                migrations.append("ADD COLUMN email VARCHAR(100)")
                print("➕ Will add email column")
            
            if 'medical_id' not in existing_columns:
                migrations.append("ADD COLUMN medical_id VARCHAR(50)")
                print("➕ Will add medical_id column")
            
            if not migrations:
                print("✅ All columns already exist. No migration needed.")
                return
            
            # Execute migration
            alter_query = f"ALTER TABLE patients {' '.join(migrations)}"
            print(f"🔧 Executing: {alter_query}")
            
            connection.execute(text(alter_query))
            connection.commit()
            
            print("✅ Database migration completed successfully!")
            
            # Verify the changes
            verify_query = """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'patients' 
            AND column_name IN ('phone', 'email', 'medical_id')
            ORDER BY column_name
            """
            
            result = connection.execute(text(verify_query))
            print("\n📋 Verification - New columns:")
            for row in result:
                print(f"   {row[0]}: {row[1]} (nullable: {row[2]})")
                
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        return False
    
    return True

def create_sample_data():
    """Create sample ESP32 device if none exists"""
    
    print("\n🔧 Checking for sample data...")
    
    engine = create_engine(DATABASE_URL)
    
    try:
        with engine.connect() as connection:
            # Check if any devices exist
            check_query = "SELECT COUNT(*) FROM esp32_devices"
            result = connection.execute(text(check_query))
            device_count = result.scalar()
            
            if device_count == 0:
                print("📱 No ESP32 devices found. Creating sample device...")
                
                # Create sample ESP32 device
                insert_query = """
                INSERT INTO esp32_devices (
                    device_id, name, device_type, location, 
                    firmware_version, ip_address, mac_address,
                    battery_level, signal_strength, is_active
                ) VALUES (
                    'ESP32_SAMPLE_001', 'ESP32 Mẫu', 'patient_monitor',
                    'Phòng 101', 'v1.0.0', '192.168.1.100',
                    'AA:BB:CC:DD:EE:FF', 100.0, -50, true
                )
                """
                
                connection.execute(text(insert_query))
                connection.commit()
                print("✅ Sample ESP32 device created successfully!")
                
            else:
                print(f"✅ Found {device_count} existing ESP32 device(s)")
                
    except Exception as e:
        print(f"⚠️ Warning: Could not create sample data: {e}")

if __name__ == "__main__":
    print("=" * 50)
    print("  Patient Monitor Database Migration")
    print("=" * 50)
    
    # Update database schema
    if update_database():
        # Create sample data
        create_sample_data()
        
        print("\n🎉 Migration completed successfully!")
        print("\n📋 Next steps:")
        print("1. Restart your Flask application")
        print("2. Try adding a patient again")
        print("3. The new fields should now work properly")
    else:
        print("\n❌ Migration failed!")
        print("Please check the error messages above")
        sys.exit(1)
