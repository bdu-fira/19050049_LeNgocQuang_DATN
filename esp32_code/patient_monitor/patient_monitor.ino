#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <Wire.h>
#include <TinyGPS++.h>
#include <WiFiClientSecure.h>
#include <DHT.h>                    // DHT11 nhiệt độ và độ ẩm phòng
#include <Adafruit_SSD1306.h>       // Màn hình OLED 0.91"
#include <Adafruit_GFX.h>           // Thư viện GFX cho OLED

// WiFi credentials - CẬP NHẬT CHO MẠNG CỦA BẠN
const char* ssid = "NasaHost";  // Tên WiFi của bạn
const char* password = "YOUR_WIFI_PASSWORD";  // ⚠️ CẬP NHẬT MẬT KHẨU WIFI THỰC TẾ CỦA BẠN

// Server configuration - CẬP NHẬT IP DOCKER HOST
const char* serverURL = "http://192.168.1.100:5000/api/sensor_data";  // ⚠️ CẬP NHẬT IP ADDRESS THỰC TẾ CỦA MÁY TÍNH
const char* deviceID = "ESP32_PATIENT_MONITOR_001";  // ID thiết bị duy nhất

// Pin definitions - Định nghĩa chân cho các cảm biến thực tế (ĐÃ SỬA XUNG ĐỘT I2C)
#define ONE_WIRE_BUS 5              // DS18B20 nhiệt độ cơ thể
#define GPS_RX_PIN 13               // GPS NEO-6M RX
#define GPS_TX_PIN 12               // GPS NEO-6M TX
#define BUZZER_PIN 32               // Loa cảnh báo
#define LED_NORMAL_PIN 33           // LED xanh (an toàn)
#define LED_WARNING_PIN 34          // LED vàng (nhắc nhở)
#define LED_CRITICAL_PIN 14         // LED đỏ (nguy hiểm)

#define DHT_PIN 15                  // DHT11 nhiệt độ và độ ẩm phòng
#define DHT_TYPE DHT11              // Loại cảm biến DHT11
#define FALL_SENSOR_PIN 4           // Cảm biến té ngã Run MHsensor series
#define ECG_LO_PLUS 26              // AD8232 Lead-Off Detection +
#define ECG_LO_MINUS 27             // AD8232 Lead-Off Detection -
#define ECG_OUTPUT 25               // AD8232 Analog Output
#define ECG_SDN 23                  // AD8232 Shutdown pin
#define EMERGENCY_BUTTON_PIN 35     // Nút nhấn cảnh báo

// I2C Pin definitions - Sử dụng 1 bus I2C duy nhất
#define I2C_SCL_PIN 18              // I2C SCL - Chia sẻ cho OLED và MH-ETLive
#define I2C_SDA_PIN 19              // I2C SDA - Chia sẻ cho OLED và MH-ETLive

// Cấu hình màn hình OLED 0.91"
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 32            // OLED 0.91" có độ cao 32px
#define OLED_RESET -1
#define SCREEN_ADDRESS 0x3C

// Timing intervals
#define SENSOR_READ_INTERVAL 1000    // Đọc cảm biến mỗi 1 giây
#define GPS_READ_INTERVAL 5000       // Đọc GPS mỗi 5 giây
#define DATA_SEND_INTERVAL 30000     // Gửi dữ liệu mỗi 30 giây
#define DISPLAY_UPDATE_INTERVAL 2000 // Cập nhật màn hình mỗi 2 giây

// ECG buffer size
#define ECG_BUFFER_SIZE 100

// Initialize sensors
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature temperatureSensor(&oneWire);
HardwareSerial gpsSerial(1); // Use UART1 for ESP32
TinyGPSPlus gps;

// Các cảm biến thực tế
DHT dht(DHT_PIN, DHT_TYPE);
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// Cấu trúc dữ liệu cảm biến
struct SensorData {
    // Dấu hiệu sinh tồn
    float heartRate = 0;            // Nhịp tim từ MH-ETLive
    float temperature = 0;          // Nhiệt độ cơ thể từ DS18B20
    float oxygenSaturation = 0;     // Độ bão hòa oxy từ MH-ETLive
    float bodyTemperature = 0;      // Nhiệt độ cơ thể
    
    // Dữ liệu phát hiện té ngã
    bool fallDetected = false;      // Từ Run MHsensor series
    float fallConfidence = 0;
    
    // Dữ liệu GPS vị trí
    double gpsLatitude = 0;
    double gpsLongitude = 0;
    float gpsAccuracy = 0;
    String roomDetected = "Unknown";
    
    // Dữ liệu môi trường
    float roomTemperature = 0;      // Nhiệt độ phòng từ DHT11
    float humidity = 0;             // Độ ẩm phòng từ DHT11
    
    // Dữ liệu điện tâm đồ
    float ecgValue = 0;             // Giá trị điện tâm đồ từ AD8232
    bool ecgLeadsConnected = false; // Trạng thái kết nối điện cực
    String ecgStatus = "Normal";    // Trạng thái ECG
    
    // Trạng thái thiết bị
    float batteryLevel = 100;
    int signalStrength = 0;
    bool emergencyButtonPressed = false; // Nút nhấn cảnh báo
    
    // Timestamps
    unsigned long lastUpdate = 0;
};

// Biến toàn cục
SensorData currentReading;
bool emergencyMode = false;
unsigned long emergencyStartTime = 0;
String patientID = "";
bool useFlaskAPIUpload = true;

// Buffer cho ECG
float ecgBuffer[ECG_BUFFER_SIZE];
int ecgBufferIndex = 0;
bool ecgBufferFull = false;

// Biến thời gian
unsigned long lastSensorRead = 0;
unsigned long lastGPSRead = 0;
unsigned long lastDataSend = 0;
unsigned long lastDisplayUpdate = 0;
unsigned long lastFallCheck = 0;

void setup() {
    Serial.begin(115200);
    Serial.println("ESP32 Patient Monitor Starting...");
    Serial.println("Sử dụng các cảm biến thực tế:");
    Serial.println("- GPS NEO-6M: Định vị vị trí");
    Serial.println("- Run MHsensor: Phát hiện té ngã");
    Serial.println("- MH-ETLive: Nhịp tim và oxy");
    Serial.println("- DHT11: Nhiệt độ và độ ẩm phòng");
    Serial.println("- AD8232: Điện tâm đồ");
    Serial.println("- DS18B20: Nhiệt độ cơ thể");
    Serial.println("- OLED 0.91\": Hiển thị thông tin");
    
    // Khởi tạo các chân
    pinMode(BUZZER_PIN, OUTPUT);
    pinMode(LED_NORMAL_PIN, OUTPUT);
    pinMode(LED_WARNING_PIN, OUTPUT);
    pinMode(LED_CRITICAL_PIN, OUTPUT);
    pinMode(FALL_SENSOR_PIN, INPUT);
    pinMode(EMERGENCY_BUTTON_PIN, INPUT_PULLUP);
    pinMode(ECG_LO_PLUS, INPUT);
    pinMode(ECG_LO_MINUS, INPUT);
    pinMode(ECG_SDN, OUTPUT);
    
    // Tắt tất cả LED ban đầu
    digitalWrite(LED_NORMAL_PIN, LOW);
    digitalWrite(LED_WARNING_PIN, LOW);
    digitalWrite(LED_CRITICAL_PIN, LOW);
    digitalWrite(BUZZER_PIN, LOW);
    
    // Khởi tạo cảm biến
    initializeSensors();
    delay(2000); // Đợi cảm biến ổn định
    
    // Khởi tạo MH-ETLive (I2C chung)
    initializeMHETLive();
    delay(1000); // Đợi I2C ổn định
    
    // Khởi tạo màn hình
    initializeDisplay();
    delay(1000); // Đợi màn hình ổn định
    
    // Kết nối WiFi
    connectToWiFi();
    
    // Lấy ID bệnh nhân từ server
    getPatientIDFromServer();
    
    Serial.println("ESP32 Patient Monitor Ready!");
}

void loop() {
    unsigned long currentTime = millis();
    
    // Đọc cảm biến định kỳ
    if (currentTime - lastSensorRead >= SENSOR_READ_INTERVAL) {
        readAllSensors();
        lastSensorRead = currentTime;
    }
    
    // Đọc GPS định kỳ
    if (currentTime - lastGPSRead >= GPS_READ_INTERVAL) {
        readGPSLocation();
        lastGPSRead = currentTime;
    }
    
    // Kiểm tra cảm biến té ngã
    if (currentTime - lastFallCheck >= 100) { // Kiểm tra mỗi 100ms
        checkFallSensor();
        lastFallCheck = currentTime;
    }
    
    // Gửi dữ liệu lên Flask server
    if (useFlaskAPIUpload && (currentTime - lastDataSend >= DATA_SEND_INTERVAL)) {
        if (WiFi.status() == WL_CONNECTED) {
            sendDataToServer();
            lastDataSend = currentTime;
        } else {
            reconnectWiFi();
        }
    }
    
    // Xử lý tình huống khẩn cấp
    handleEmergencyMode();
    
    // Xử lý nút nhấn cảnh báo
    handleEmergencyButton();
    
    // Xử lý lệnh serial
    handleSerialCommands();
    
    // Cập nhật màn hình
    if (currentTime - lastDisplayUpdate >= DISPLAY_UPDATE_INTERVAL) {
        updateDisplay();
        lastDisplayUpdate = currentTime;
    }
    
    delay(10);
}

// Kết nối WiFi
void connectToWiFi() {
    Serial.print("Kết nối WiFi: ");
    Serial.println(ssid);
    
    // Reset WiFi trước khi kết nối
    WiFi.disconnect();
    WiFi.mode(WIFI_STA);
    delay(1000);
    
    WiFi.begin(ssid, password);
    
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 30) {
        delay(1000);
        Serial.print(".");
        attempts++;
        
        // Kiểm tra nếu quá lâu
        if (attempts > 20) {
            Serial.println("\nThử kết nối lại...");
            WiFi.disconnect();
            delay(2000);
            WiFi.begin(ssid, password);
            attempts = 0;
        }
    }
    
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\nWiFi đã kết nối!");
        Serial.print("IP address: ");
        Serial.println(WiFi.localIP());
        
        // Cập nhật cường độ tín hiệu
        currentReading.signalStrength = WiFi.RSSI();
    } else {
        Serial.println("\nKết nối WiFi thất bại!");
        setStatusLED("error");
    }
}

// Kết nối lại WiFi
void reconnectWiFi() {
    Serial.println("Kết nối lại WiFi...");
    WiFi.disconnect();
    delay(1000);
    connectToWiFi();
}

// Lấy ID bệnh nhân từ Flask server
void getPatientIDFromServer() {
    if (WiFi.status() != WL_CONNECTED) return;
    
    HTTPClient http;
    String getPatientURL = String(serverURL).substring(0, String(serverURL).lastIndexOf('/')) + "/patient_status/" + String(deviceID);
    http.begin(getPatientURL);
    
    int httpResponseCode = http.GET();
    
    if (httpResponseCode == 200) {
        String response = http.getString();
        
        StaticJsonDocument<300> doc;
        DeserializationError error = deserializeJson(doc, response);
        
        if (!error) {
            patientID = doc["patient_id"].as<String>();
            Serial.println("Patient ID: " + patientID);
        }
    } else {
        Serial.println("Không thể lấy Patient ID từ server: " + String(httpResponseCode));
        // Sử dụng device ID làm dự phòng
        patientID = deviceID;
    }
    
    http.end();
}

// Tính toán mức độ cảnh báo dựa trên dấu hiệu sinh tồn
String calculateAlertLevel() {
    String alertLevel = "normal";
    
    // Kiểm tra nhịp tim
    if (currentReading.heartRate > 0) {
        if (currentReading.heartRate < 60 || currentReading.heartRate > 100) {
            alertLevel = "warning";
        }
        if (currentReading.heartRate < 40 || currentReading.heartRate > 120) {
            alertLevel = "critical";
        }
    }
    
    // Kiểm tra nhiệt độ cơ thể
    if (currentReading.bodyTemperature > 0) {
        if (currentReading.bodyTemperature < 36 || currentReading.bodyTemperature > 38) {
            alertLevel = "warning";
        }
        if (currentReading.bodyTemperature < 35 || currentReading.bodyTemperature > 39) {
            alertLevel = "critical";
        }
    }
    
    // Kiểm tra độ bão hòa oxy
    if (currentReading.oxygenSaturation > 0) {
        if (currentReading.oxygenSaturation < 95) {
            alertLevel = "warning";
        }
        if (currentReading.oxygenSaturation < 90) {
            alertLevel = "critical";
        }
    }
    
    // Phát hiện té ngã ghi đè tất cả
    if (currentReading.fallDetected) {
        alertLevel = "critical";
    }
    
    // Nút nhấn cảnh báo
    if (currentReading.emergencyButtonPressed) {
        alertLevel = "critical";
    }
    
    return alertLevel;
}

// Khởi tạo tất cả cảm biến
void initializeSensors() {
    Serial.println("Khởi tạo cảm biến...");
    
    // Khởi tạo cảm biến nhiệt độ DS18B20
    temperatureSensor.begin();
    Serial.println("- DS18B20 (nhiệt độ cơ thể) đã khởi tạo");
    
    // Khởi tạo GPS NEO-6M
    gpsSerial.begin(9600, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);
    Serial.println("- GPS NEO-6M đã khởi tạo");
    
    // Khởi tạo DHT11
    dht.begin();
    Serial.println("- DHT11 (nhiệt độ và độ ẩm phòng) đã khởi tạo");

    // Khởi tạo ECG (AD8232)
    pinMode(ECG_OUTPUT, INPUT); // AD8232 output là analog input
    pinMode(ECG_SDN, OUTPUT);
    digitalWrite(ECG_SDN, HIGH); // Đảm bảo AD8232 tắt
    Serial.println("- ECG (AD8232) đã khởi tạo");
    
    // Khởi tạo buffer ECG
    for (int i = 0; i < ECG_BUFFER_SIZE; i++) {
        ecgBuffer[i] = 0;
    }
    
    Serial.println("Tất cả cảm biến đã được khởi tạo");
}

// Khởi tạo MH-ETLive - I2C chung
void initializeMHETLive() {
    // Sử dụng I2C chung đã được khởi tạo
    
    // Kiểm tra kết nối MH-ETLive
    Wire.beginTransmission(0x57); // Địa chỉ I2C mặc định
    byte error = Wire.endTransmission();
    
    if (error == 0) {
        Serial.println("- MH-ETLive đã khởi tạo (I2C chung)");
    } else {
        Serial.println("- Lỗi kết nối MH-ETLive (I2C chung)");
    }
}

// Khởi tạo màn hình OLED 0.91" - I2C chung
void initializeDisplay() {
    // Khởi tạo I2C chung cho OLED và MH-ETLive
    Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
    
    if(!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
        Serial.println(F("Không thể khởi tạo SSD1306"));
        for(;;);
    }
    display.display();
    delay(2000); // Tạm dừng
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 0);
    display.println("ESP32 Patient");
    display.println("Monitor");
    display.display();
    delay(2000);
    display.clearDisplay();
    
    Serial.println("- OLED 0.91\" đã khởi tạo (I2C chung)");
}

// Cập nhật màn hình
void updateDisplay() {
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("ESP32 Patient Monitor");
    
    display.setTextSize(1);
    display.setCursor(0, 10);
    display.print("HR: ");
    display.print(currentReading.heartRate);
    display.print(" bpm");
    
    display.setCursor(0, 20);
    display.print("Temp: ");
    display.print(currentReading.bodyTemperature);
    display.print("C");
    
    display.setCursor(64, 10);
    display.print("O2: ");
    display.print(currentReading.oxygenSaturation);
    display.print("%");
    
    display.setCursor(64, 20);
    display.print("Room: ");
    display.print(currentReading.roomDetected);
    
    display.display();
}

// Đọc tất cả cảm biến
void readAllSensors() {
    // Đọc nhiệt độ cơ thể từ DS18B20
    temperatureSensor.requestTemperatures();
    currentReading.bodyTemperature = temperatureSensor.getTempCByIndex(0);
    
    // Đọc nhiệt độ và độ ẩm phòng từ DHT11
    currentReading.roomTemperature = dht.readTemperature();
    currentReading.humidity = dht.readHumidity();
    
    // Đọc điện tâm đồ
    readECG();
    
    // Cập nhật mức pin (mô phỏng)
    currentReading.batteryLevel = max(0, currentReading.batteryLevel - 0.01);
    
    // Cập nhật cường độ tín hiệu
    if (WiFi.status() == WL_CONNECTED) {
        currentReading.signalStrength = WiFi.RSSI();
    }
    
    currentReading.lastUpdate = millis();
}

// Đọc dữ liệu ECG
void readECG() {
    // Kiểm tra điện cực có được kết nối
    bool loPlus = digitalRead(ECG_LO_PLUS);
    bool loMinus = digitalRead(ECG_LO_MINUS);
    
    currentReading.ecgLeadsConnected = !(loPlus || loMinus);
    
    if (currentReading.ecgLeadsConnected) {
        // Đọc giá trị ECG
        currentReading.ecgValue = analogRead(ECG_OUTPUT);
        
        // Lưu vào buffer
        ecgBuffer[ecgBufferIndex] = currentReading.ecgValue;
        ecgBufferIndex = (ecgBufferIndex + 1) % ECG_BUFFER_SIZE;
        
        if (ecgBufferIndex == 0) {
            ecgBufferFull = true;
        }
        
        // Phân tích trạng thái ECG
        if (currentReading.ecgValue > 2000) {
            currentReading.ecgStatus = "High";
        } else if (currentReading.ecgValue < 500) {
            currentReading.ecgStatus = "Low";
        } else {
            currentReading.ecgStatus = "Normal";
        }
    } else {
        currentReading.ecgValue = 0;
        currentReading.ecgStatus = "No Signal";
    }
}

// Kiểm tra cảm biến té ngã Run MHsensor series
void checkFallSensor() {
    bool fallSignal = digitalRead(FALL_SENSOR_PIN);
    
    if (fallSignal == HIGH) {
        if (!currentReading.fallDetected) {
            currentReading.fallDetected = true;
            currentReading.fallConfidence = 0.9;
            Serial.println("PHÁT HIỆN TÉ NGÃ!");
            triggerEmergency("FALL_DETECTED");
        }
    } else {
        currentReading.fallDetected = false;
    }
}

// Xử lý nút nhấn cảnh báo
void handleEmergencyButton() {
    static bool lastButtonState = HIGH;
    bool currentButtonState = digitalRead(EMERGENCY_BUTTON_PIN);
    
    // Phát hiện nhấn nút (nhấp nhả)
    if (lastButtonState == HIGH && currentButtonState == LOW) {
        currentReading.emergencyButtonPressed = true;
        Serial.println("NÚT CẢNH BÁO ĐƯỢC NHẤN!");
        triggerEmergency("EMERGENCY_BUTTON");
        delay(50); // Chống dội phím
    }
    
    // Reset trạng thái nút
    if (lastButtonState == LOW && currentButtonState == HIGH) {
        currentReading.emergencyButtonPressed = false;
    }
    
    lastButtonState = currentButtonState;
}

// Đọc vị trí GPS
void readGPSLocation() {
    while (gpsSerial.available() > 0) {
        if (gps.encode(gpsSerial.read())) {
            if (gps.location.isValid()) {
                currentReading.gpsLatitude = gps.location.lat();
                currentReading.gpsLongitude = gps.location.lng();
                currentReading.gpsAccuracy = gps.hdop.hdop();
                
                // Xác định phòng dựa trên tọa độ GPS
                currentReading.roomDetected = determineRoom(currentReading.gpsLatitude, currentReading.gpsLongitude);
                
                Serial.println("GPS: " + String(currentReading.gpsLatitude, 6) + ", " + 
                             String(currentReading.gpsLongitude, 6) + " - Phòng: " + currentReading.roomDetected);
            }
        }
    }
}

// Xác định phòng dựa trên tọa độ GPS
String determineRoom(double latitude, double longitude) {
    // Ví dụ tọa độ cho khu vực TP.HCM
    if (latitude >= 10.7756 && latitude <= 10.7757 && longitude >= 106.7017 && longitude <= 106.7018) {
        return "Phong 101";
    } else if (latitude >= 10.7757 && latitude <= 10.7758 && longitude >= 106.7017 && longitude <= 106.7018) {
        return "Phong 102";
    } else if (latitude >= 10.7758 && latitude <= 10.7759 && longitude >= 106.7017 && longitude <= 106.7018) {
        return "Phong 103";
    } else if (latitude >= 10.7759 && latitude <= 10.7760 && longitude >= 106.7017 && longitude <= 106.7018) {
        return "Phong Cap Cuu";
    } else if (latitude >= 10.7760 && latitude <= 10.7761 && longitude >= 106.7017 && longitude <= 106.7018) {
        return "ICU";
    }
    return "Phong Khong Xac Dinh";
}

// Gửi dữ liệu lên Flask server
void sendDataToServer() {
    if (WiFi.status() != WL_CONNECTED) {
        return;
    }
    
    HTTPClient http;
    http.begin(serverURL);
    http.addHeader("Content-Type", "application/json");
    
    // Tạo JSON payload đầy đủ
    StaticJsonDocument<800> doc;
    doc["device_id"] = deviceID;
    
    // Dấu hiệu sinh tồn
    doc["heart_rate"] = currentReading.heartRate;
    doc["temperature"] = currentReading.bodyTemperature;
    doc["oxygen_saturation"] = currentReading.oxygenSaturation;
    
    // Dữ liệu phát hiện té ngã
    doc["fall_detected"] = currentReading.fallDetected;
    doc["fall_confidence"] = currentReading.fallConfidence;
    
    // Dữ liệu GPS
    doc["gps_lat"] = currentReading.gpsLatitude;
    doc["gps_lng"] = currentReading.gpsLongitude;
    doc["gps_accuracy"] = currentReading.gpsAccuracy;
    doc["room_detected"] = currentReading.roomDetected;
    
    // Dữ liệu môi trường
    doc["room_temperature"] = currentReading.roomTemperature;
    doc["humidity"] = currentReading.humidity;
    
    // Dữ liệu điện tâm đồ
    doc["ecg_value"] = currentReading.ecgValue;
    doc["ecg_leads_connected"] = currentReading.ecgLeadsConnected;
    doc["ecg_status"] = currentReading.ecgStatus;
    
    // Dữ liệu ECG buffer (nếu có)
    if (ecgBufferFull && currentReading.ecgLeadsConnected) {
        doc["ecg_data"] = getECGDataString();
    }
    
    // Trạng thái thiết bị
    doc["battery_level"] = currentReading.batteryLevel;
    doc["signal_strength"] = currentReading.signalStrength;
    doc["emergency_button_pressed"] = currentReading.emergencyButtonPressed;
    
    String jsonString;
    serializeJson(doc, jsonString);
    
    Serial.println("Gửi dữ liệu lên Flask server...");
    Serial.println("JSON: " + jsonString);
    
    int httpResponseCode = http.POST(jsonString);
    
    if (httpResponseCode > 0) {
        String response = http.getString();
        Serial.println("Phản hồi Flask server: " + String(httpResponseCode));
        Serial.println("Nội dung: " + response);
        
        // Phân tích phản hồi để lấy cảnh báo
        StaticJsonDocument<300> responseDoc;
        DeserializationError error = deserializeJson(responseDoc, response);
        
        if (!error) {
            String alertLevel = responseDoc["alert_level"];
            bool fallDetected = responseDoc["fall_detected"];
            
            setStatusLED(alertLevel);
            
            if (alertLevel == "critical" || fallDetected) {
                triggerEmergency("SERVER_ALERT");
            }
        }
    } else {
        Serial.println("Lỗi gửi dữ liệu lên Flask: " + String(httpResponseCode));
        setStatusLED("error");
    }
    
    http.end();
}

// Lấy dữ liệu ECG dưới dạng chuỗi để truyền
String getECGDataString() {
    String ecgData = "";
    for (int i = 0; i < ECG_BUFFER_SIZE; i++) {
        if (i > 0) ecgData += ",";
        ecgData += String(ecgBuffer[i]);
    }
    return ecgData;
}

// Đặt LED trạng thái dựa trên điều kiện
void setStatusLED(String status) {
    // Tắt tất cả LED trước
    digitalWrite(LED_NORMAL_PIN, LOW);
    digitalWrite(LED_WARNING_PIN, LOW);
    digitalWrite(LED_CRITICAL_PIN, LOW);
    
    if (status == "normal") {
        digitalWrite(LED_NORMAL_PIN, HIGH);      // LED xanh - an toàn
    } else if (status == "warning") {
        digitalWrite(LED_WARNING_PIN, HIGH);     // LED vàng - nhắc nhở
    } else if (status == "critical") {
        digitalWrite(LED_CRITICAL_PIN, HIGH);    // LED đỏ - nguy hiểm
    } else if (status == "error") {
        // Nhấp nháy LED đỏ cho lỗi
        digitalWrite(LED_CRITICAL_PIN, millis() % 500 < 250);
    }
}

// Kích hoạt chế độ khẩn cấp
void triggerEmergency(String reason) {
    if (!emergencyMode) {
        emergencyMode = true;
        emergencyStartTime = millis();
        Serial.println("CHẾ ĐỘ KHẨN CẤP: " + reason);
        
        // Phát âm thanh cảnh báo
        for (int i = 0; i < 5; i++) {
            digitalWrite(BUZZER_PIN, HIGH);
            delay(200);
            digitalWrite(BUZZER_PIN, LOW);
            delay(200);
        }
        
        // Gửi cảnh báo khẩn cấp lên Flask server
        if (useFlaskAPIUpload) {
            sendEmergencyAlert(reason);
        }
    }
}

// Gửi cảnh báo khẩn cấp lên Flask server
void sendEmergencyAlert(String reason) {
    if (WiFi.status() != WL_CONNECTED) {
        return;
    }
    
    HTTPClient http;
    http.begin(serverURL);
    http.addHeader("Content-Type", "application/json");
    
    StaticJsonDocument<400> emergencyDoc;
    emergencyDoc["device_id"] = deviceID;
    emergencyDoc["emergency"] = true;
    emergencyDoc["emergency_reason"] = reason;
    emergencyDoc["timestamp"] = millis();
    
    // Bao gồm dấu hiệu sinh tồn hiện tại
    emergencyDoc["heart_rate"] = currentReading.heartRate;
    emergencyDoc["temperature"] = currentReading.bodyTemperature;
    emergencyDoc["fall_detected"] = currentReading.fallDetected;
    emergencyDoc["ecg_leads_connected"] = currentReading.ecgLeadsConnected;
    emergencyDoc["gps_lat"] = currentReading.gpsLatitude;
    emergencyDoc["gps_lng"] = currentReading.gpsLongitude;
    emergencyDoc["room_detected"] = currentReading.roomDetected;
    
    String emergencyJson;
    serializeJson(emergencyDoc, emergencyJson);
    
    int httpResponseCode = http.POST(emergencyJson);
    Serial.println("Cảnh báo khẩn cấp đã gửi: " + String(httpResponseCode));
    
    http.end();
}

// Xử lý chế độ khẩn cấp
void handleEmergencyMode() {
    if (emergencyMode) {
        // Nhấp nháy LED đỏ
        digitalWrite(LED_CRITICAL_PIN, millis() % 500 < 250);
        
        // Kiểm tra xem khẩn cấp có nên kết thúc (sau 30 giây)
        if (millis() - emergencyStartTime > 30000) {
            emergencyMode = false;
            Serial.println("Chế độ khẩn cấp đã kết thúc");
            setStatusLED(calculateAlertLevel());
        }
    }
}

// Xử lý lệnh serial
void handleSerialCommands() {
    if (Serial.available()) {
        String command = Serial.readStringUntil('\n');
        command.trim();
        
        if (command == "status") {
            printStatus();
        } else if (command == "test") {
            testSensors();
        } else if (command == "wifi") {
            printWiFiStatus();
        } else if (command == "help") {
            printHelp();
        }
    }
}

// In trạng thái hệ thống
void printStatus() {
    Serial.println("=== Trạng thái ESP32 Patient Monitor ===");
    Serial.println("Device ID: " + String(deviceID));
    Serial.println("Patient ID: " + patientID);
    Serial.println("Trạng thái WiFi: " + String(WiFi.status() == WL_CONNECTED ? "Đã kết nối" : "Mất kết nối"));
    Serial.println("IP Address: " + WiFi.localIP().toString());
    Serial.println("Cường độ tín hiệu: " + String(currentReading.signalStrength) + " dBm");
    Serial.println("Mức pin: " + String(currentReading.batteryLevel) + "%");
    Serial.println("Chế độ khẩn cấp: " + String(emergencyMode ? "CÓ" : "KHÔNG"));
    Serial.println("Phát hiện té ngã: " + String(currentReading.fallDetected ? "CÓ" : "KHÔNG"));
    Serial.println("Nút cảnh báo: " + String(currentReading.emergencyButtonPressed ? "ĐÃ NHẤN" : "CHƯA NHẤN"));
    
    Serial.println("--- Pin Mapping (I2C chung) ---");
    Serial.println("OLED và MH-ETLive: GPIO " + String(I2C_SCL_PIN) + "/" + String(I2C_SDA_PIN) + " (I2C chung)");
    Serial.println("========================================");
}

// Kiểm tra cảm biến
void testSensors() {
    Serial.println("=== Kiểm tra cảm biến ===");
    
    // Kiểm tra nhiệt độ cơ thể
    temperatureSensor.requestTemperatures();
    float temp = temperatureSensor.getTempCByIndex(0);
    Serial.println("Nhiệt độ cơ thể (DS18B20): " + String(temp) + "°C");
    
    // Kiểm tra DHT11
    float dhtTemp = dht.readTemperature();
    float dhtHum = dht.readHumidity();
    Serial.println("Nhiệt độ phòng (DHT11): " + String(dhtTemp) + "°C");
    Serial.println("Độ ẩm phòng (DHT11): " + String(dhtHum) + "%");
    
    // Kiểm tra cảm biến té ngã
    bool fall = digitalRead(FALL_SENSOR_PIN);
    Serial.println("Cảm biến té ngã (Run MHsensor): " + String(fall ? "CÓ TÍN HIỆU" : "KHÔNG CÓ TÍN HIỆU"));
    
    // Kiểm tra nút cảnh báo
    bool button = digitalRead(EMERGENCY_BUTTON_PIN);
    Serial.println("Nút cảnh báo: " + String(button ? "CHƯA NHẤN" : "ĐÃ NHẤN"));
    
    // Kiểm tra điện cực ECG
    bool loPlus = digitalRead(ECG_LO_PLUS);
    bool loMinus = digitalRead(ECG_LO_MINUS);
    Serial.println("Điện cực ECG kết nối: " + String(!(loPlus || loMinus) ? "CÓ" : "KHÔNG"));
    
    // Kiểm tra I2C
    Serial.println("--- Kiểm tra I2C ---");
    Serial.println("OLED 0.91\" và MH-ETLive: GPIO " + String(I2C_SCL_PIN) + " (SCL), " + String(I2C_SDA_PIN) + " (SDA)");
    
    Serial.println("=======================");
}

// In trạng thái WiFi
void printWiFiStatus() {
    Serial.println("=== Trạng thái WiFi ===");
    Serial.println("SSID: " + String(ssid));
    Serial.println("Trạng thái: " + String(WiFi.status() == WL_CONNECTED ? "Đã kết nối" : "Mất kết nối"));
    Serial.println("IP: " + WiFi.localIP().toString());
    Serial.println("RSSI: " + String(WiFi.RSSI()) + " dBm");
    Serial.println("=====================");
}

// In trợ giúp
void printHelp() {
    Serial.println("=== Lệnh có sẵn ===");
    Serial.println("status - Hiển thị trạng thái hệ thống");
    Serial.println("test   - Kiểm tra tất cả cảm biến");
    Serial.println("wifi   - Hiển thị trạng thái WiFi");
    Serial.println("help   - Hiển thị trợ giúp này");
    Serial.println("");
    Serial.println("=== Pin Mapping (I2C chung) ===");
    Serial.println("OLED 0.91\" và MH-ETLive: GPIO " + String(I2C_SCL_PIN) + " (SCL), " + String(I2C_SDA_PIN) + " (SDA) - I2C chung");
    Serial.println("========================================");
} 