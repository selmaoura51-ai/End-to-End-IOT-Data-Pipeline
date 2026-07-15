# End-to-End IoT Data Pipeline

A scalable and professional IoT data pipeline designed for high-throughput telemetry simulation, data processing, and validation.

## 🚀 Project Overview
This project establishes a core infrastructure to simulate, capture, and output real-time sensor data. It bridges low-level system performance with high-level data scripting to guarantee zero-loss data pipelines.

## 🛠️ Tech Stack & Architecture
- **C++ Component (`test.cpp`)**: Handles core performance simulation and continuous data compilation.
- **Python Component (`test.py`)**: Manages telemetry ingestion, data manipulation, and pipeline verification.
- **Data Log (`test_output`)**: Verified execution output showcasing stable data flow.

## ⚡ Quick Start
To run the telemetry simulation locally, execute the following commands in your terminal:

```bash
# Compile and run the C++ simulator
g++ test.cpp -o simulator
./simulator

# Execute the Python data pipeline script
python3 test.py
```

## 📈 Future Roadmap
- [ ] Implement MQTT protocol for real-time broker messaging.
- [ ] Integrate Docker containers for isolated microservices.
- [ ] Connect cloud database storage (InfluxDB / PostgreSQL) for historical indexing.                                                                                                                                                                                                  
