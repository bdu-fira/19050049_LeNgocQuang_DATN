-- Patient Monitor Database Migration
-- Adds new columns to patients table: phone, email, medical_id

-- Kiểm tra columns hiện có
SELECT 'Current columns in patients table:' as info;
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'patients' 
ORDER BY ordinal_position;

-- Thêm columns mới (chỉ thêm nếu chưa tồn tại)
DO $$
BEGIN
    -- Thêm phone column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'patients' AND column_name = 'phone') THEN
        ALTER TABLE patients ADD COLUMN phone VARCHAR(20);
        RAISE NOTICE 'Added phone column';
    ELSE
        RAISE NOTICE 'phone column already exists';
    END IF;
    
    -- Thêm email column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'patients' AND column_name = 'email') THEN
        ALTER TABLE patients ADD COLUMN email VARCHAR(100);
        RAISE NOTICE 'Added email column';
    ELSE
        RAISE NOTICE 'email column already exists';
    END IF;
    
    -- Thêm medical_id column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'patients' AND column_name = 'medical_id') THEN
        ALTER TABLE patients ADD COLUMN medical_id VARCHAR(50);
        RAISE NOTICE 'Added medical_id column';
    ELSE
        RAISE NOTICE 'medical_id column already exists';
    END IF;
END $$;

-- Xác nhận thay đổi
SELECT 'Updated columns in patients table:' as info;
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'patients' 
ORDER BY ordinal_position;

-- Kiểm tra columns mới
SELECT 'New columns verification:' as info;
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'patients' 
AND column_name IN ('phone', 'email', 'medical_id')
ORDER BY column_name;
