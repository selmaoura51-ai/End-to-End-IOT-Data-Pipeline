cat << 'EOF' > test.py
import paho.mqtt.client as mqtt
import sqlite3
import json
from datetime import datetime

DB_NAME = "iot_pipeline.db"

def init_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS telemetry_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            temperature REAL NOT NULL,
            battery_status TEXT NOT NULL,
            recorded_at TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fault_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            dtc_code TEXT NOT NULL,
            severity TEXT NOT NULL,
            logged_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    print("[INFO] Database layers initialized successfully.")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        device_id = payload.get("device_id")
        telemetry = payload.get("telemetry", {})
        temperature = telemetry.get("temperature")
        battery_status = telemetry.get("battery_status")
        diagnostics = payload.get("diagnostics", {})
        has_fault = diagnostics.get("has_fault", False)
        dtc_code = diagnostics.get("dtc_code", "None")
        severity = diagnostics.get("severity", "NONE")
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO telemetry_data (device_id, temperature, battery_status, recorded_at) VALUES (?, ?, ?, ?)",
            (device_id, temperature, battery_status, current_time)
        )
        if has_fault:
            cursor.execute(
                "INSERT INTO fault_logs (device_id, dtc_code, severity, logged_at) VALUES (?, ?, ?, ?)",
                (device_id, dtc_code, severity, current_time)
            )
            print(f"[ALERT] Edge fault verified -> Code: {dtc_code} | Severity: {severity}")
            client.publish("selma/automotive/control", "FAN_ON")
        else:
            client.publish("selma/automotive/control", "FAN_OFF")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[ERROR] Process failed: {e}")

if __name__ == "__main__":
    init_database()
    client = mqtt.Client()
    client.on_message = on_message
    client.connect("broker.emqx.io", 1883, 60)
    client.subscribe("selma/automotive/telemetry")
    print("[INFO] Server pipeline is live and waiting for MQTT data...")
    client.loop_forever()
EOF