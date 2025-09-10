#!/usr/bin/env python3
"""
Simple Database Migration Script for Docker Container
Adds new columns to patients table: phone, email, medical_id
"""

import os
from sqlalchemy import create_engine, text

# Database connection for Docker container
DATABASE_URL = 'postgresql://patient_user:patient_password@postgres:5432/patient_monitor'

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
                return True
            
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

if __name__ == "__main__":
    print("=" * 50)
    print("  Patient Monitor Database Migration")
    print("=" * 50)
    
    if update_database():
        print("\n🎉 Migration completed successfully!")
        print("You can now restart your Flask application")
    else:
        print("\n❌ Migration failed!")
        exit(1)
