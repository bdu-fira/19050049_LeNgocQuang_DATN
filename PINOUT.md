# Sơ đồ chân (Pinout) dự án ESP32 Patient Monitor

Dưới đây là bảng tổng hợp các chân (pin) được sử dụng trong dự án, dựa trên file `patient_monitor.ino`:

| Tên chức năng           | Tên biến mã | Chân ESP32 |
|-------------------------|-------------|------------|
| DS18B20 (Nhiệt độ cơ thể) | ONE_WIRE_BUS | 5          |
| GPS NEO-6M RX           | GPS_RX_PIN  | 13         |
| GPS NEO-6M TX           | GPS_TX_PIN  | 12         |
| Loa cảnh báo (Buzzer)   | BUZZER_PIN  | 32         |
| LED xanh (an toàn)      | LED_NORMAL_PIN | 33      |
| LED vàng (nhắc nhở)     | LED_WARNING_PIN | 34     |
| LED đỏ (nguy hiểm)      | LED_CRITICAL_PIN | 14    |
| DHT11 (Nhiệt độ, độ ẩm phòng) | DHT_PIN | 15      |
| Cảm biến té ngã         | FALL_SENSOR_PIN | 4      |
| AD8232 Lead-Off +       | ECG_LO_PLUS | 26         |
| AD8232 Lead-Off -       | ECG_LO_MINUS | 27        |
| AD8232 Analog Output    | ECG_OUTPUT  | 25         |
| AD8232 Shutdown         | ECG_SDN     | 23         |
| Nút nhấn cảnh báo       | EMERGENCY_BUTTON_PIN | 35 |
| I2C SCL (OLED, MH-ETLive) | I2C_SCL_PIN | 18      |
| I2C SDA (OLED, MH-ETLive) | I2C_SDA_PIN | 19      |

**Lưu ý:**
- Các chân I2C (SCL/SDA) dùng chung cho màn hình OLED và các thiết bị I2C khác.
- Các chân có thể thay đổi tùy theo phần cứng thực tế, hãy kiểm tra lại sơ đồ mạch của bạn.

---

*File này được tạo tự động từ mã nguồn dự án.*
