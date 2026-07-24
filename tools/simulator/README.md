# LivestockGuard Device Simulator

Simulates GPS livestock tags sending telemetry to the cloud backend.
Used for development and testing without real hardware.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Simulate 10 animals on a farm near Bloemfontein
python simulator.py --animals 10 --farm-lat -29.12 --farm-lon 26.21

# Simulate a theft scenario
python simulator.py --animals 5 --scenario theft

# Simulate a geofence breach
python simulator.py --animals 5 --scenario breach
```

## Scenarios

- `normal` — Animals grazing normally within fences
- `breach` — One animal gradually moves outside geofence
- `theft` — One animal suddenly accelerates to 60+ km/h
- `night` — Movement detected during quiet hours
- `low_battery` — Battery drain simulation

## MQTT Broker

By default connects to `localhost:1883` (Docker Compose EMQX).
Override with `--broker` and `--port` flags.
