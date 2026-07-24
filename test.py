import paho.mqtt.client as mqtt
import sqlite3
import json
import smtplib
from email.mime.text import MIMEText
import time
from datetime import datetime

# =====================================================================
# 1. Configurations
# =====================================================================
ADAFRUIT_USERNAME = "MY_ADAFRUIT_USERNAME"
ADAFRUIT_KEY = "MY_ADAFRUIT_KEY"
ADAFRUIT_FEED_TEMP = f"{ADAFRUIT_USERNAME}/feeds/temperature"

SENDER_EMAIL = "MY_SENDER_EMAIL"
SENDER_PASSWORD = "MY_SENDER_PADDWORD"
RECEIVER_EMAIL = "MY_RECEIVER_EMAIL"

last_alert_time = 0
ALERT_COOLDOWN = 60

MQTT_BROKER = "broker.emqx.io"
TOPIC_TELEMETRY = "selma/automotive/telemetry"
TOPIC_CONTROL = "selma/automotive/control"

# =====================================================================
# 2. Adafruit IO Connection
# =====================================================================
try:
    aio_client = mqtt.Client()
    aio_client.username_pw_set(ADAFRUIT_USERNAME, ADAFRUIT_KEY)
    aio_client.connect("io.adafruit.com", 1883, 60)
    aio_client.loop_start()
    print("[INIT] Connected to Adafruit IO Cloud Successfully.")
except Exception as e:
    print(f"[INIT ERROR] Failed to connect to Adafruit IO: {e}")

# =====================================================================
# 3. SQLite Database Setup
# =====================================================================
def init_database():
    conn = sqlite3.connect("iot_pipeline.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telemetry_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT,
            temperature REAL,
            battery_status TEXT,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fault_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT,
            dtc_code TEXT,
            severity TEXT,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    print("[DATABASE] SQLite tables initialized successfully.")

# =====================================================================
# 4. Email Alert Function
# =====================================================================
def send_email_alert(device_id, dtc_code, severity, temperature):
    global last_alert_time
    current_time = time.time()
    
    if not SENDER_PASSWORD:
        print("[SMTP] Email alerts disabled: App Password is empty.")
        return

    if current_time - last_alert_time < ALERT_COOLDOWN:
        print("[SMTP] Alert skipped due to cooldown protection.")
        return

    subject = "⚠️ SYSTEM CRITICAL ALERT - IoT Vehicle Pipeline"
    body = f"""
CRITICAL FAULT DETECTED IN EDGE NODE
====================================
Device ID: {device_id}
Fault Code (DTC): {dtc_code}
Severity Level: {severity}
Current Temperature: {temperature}°C
Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
====================================
Automated Action Taken: Cooling fan command sent immediately.
"""

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
            
        last_alert_time = current_time
        print(f"[SMTP] Critical Email alert sent successfully to {RECEIVER_EMAIL}.")
    except Exception as e:
        print(f"[SMTP ERROR] Failed to send email: {e}")

# =====================================================================
# 5. MQTT On Message Processing
# =====================================================================
def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        
        device_id = payload.get("device_id")
        telemetry = payload.get("telemetry", {})
        temperature = telemetry.get("temperature")
        battery_status = telemetry.get("battery_status")
        
        diagnostics = payload.get("diagnostics", {})
        dtc_code = diagnostics.get("dtc_code")
        severity = diagnostics.get("severity")
        has_fault = diagnostics.get("has_fault", False)
        
        print(f"\n[MQTT Received] Device: {device_id} | Temp: {temperature}°C | Fault: {has_fault}")

        if temperature is not None:
            try:
                aio_client.publish(ADAFRUIT_FEED_TEMP, str(temperature))
                print("[Dashboard] Telemetry streamed to Adafruit IO Feed.")
            except Exception as dashboard_err:
                print(f"[Dashboard ERROR] Cloud publishing failed: {dashboard_err}")

        conn = sqlite3.connect("iot_pipeline.db")
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO telemetry_data (device_id, temperature, battery_status) VALUES (?, ?, ?)",
            (device_id, temperature, battery_status)
        )

        if has_fault or (temperature is not None and temperature > 40):
            client.publish(TOPIC_CONTROL, "FAN_ON")
            print("[Actuation] Critical threshold breached! Command 'FAN_ON' dispatched.")
            
            cursor.execute(
                "INSERT INTO fault_logs (device_id, dtc_code, severity) VALUES (?, ?, ?)",
                (device_id, dtc_code if dtc_code else "P0115", severity if severity else "HIGH")
            )
            
            send_email_alert(device_id, dtc_code if dtc_code else "P0115", severity if severity else "HIGH", temperature)
        else:
            client.publish(TOPIC_CONTROL, "FAN_OFF")

        conn.commit()
        conn.close()

    except Exception as e:
        print(f"[PROCESS ERROR] Data pipeline parsing failed: {e}")

# =====================================================================
# 6. Main Execution
# =====================================================================
if __name__ == "__main__":
    print("==============================================")
    print(" Starting Smart Vehicle IoT Backend Server ")
    print("==============================================")
    
    init_database()
    
    local_client = mqtt.Client()
    local_client.on_message = on_message

    try:
        local_client.connect(MQTT_BROKER, 1883, 60)
        local_client.subscribe(TOPIC_TELEMETRY)
        print(f"[MQTT INIT] Subscribed to '{TOPIC_TELEMETRY}' on {MQTT_BROKER}")
        
        local_client.loop_forever()
        
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Server stopped manually by user.")
    except Exception as e:
        print(f"[FATAL ERROR] MQTT execution collapsed: {e}")