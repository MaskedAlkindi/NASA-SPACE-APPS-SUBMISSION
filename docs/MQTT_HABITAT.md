# Habitat sensors over MQTT

Any sensor or gateway that can publish MQTT can feed HEALTH-01: ESP32, Raspberry Pi, Home Assistant, Node-RED or industrial gateways.

## 1. Broker

A broker (Mosquitto) starts with the stack:

```bash
docker compose up -d
```

| Setting | Value |
|---|---|
| From your network | `<computer-ip>:1883` |
| Inside Docker | `mosquitto:1883` |
| Online server | the broker is bound to localhost; reach it over an SSH tunnel or VPN |

You can also use your own broker: set its host, port, username, password and TLS on the page.

## 2. Connect

**Connect › Habitat sensors**, then **Broker**. Check the host (`mosquitto`), leave *Listen for topics* as `habitat/#`, and press **Connect**.

## 3. Publish

Any topic under `habitat/` works. The payload can be a number or JSON:

```
habitat/module-a/co2        2650
habitat/module-a/climate    {"t": 22.4, "rh": 46}
```

## Live simulated pipeline

A separate module publishes simulated cabin readings into the broker. It does not start with `docker compose up`. With the main stack already running:

```powershell
.\scripts\mqtt_sim.ps1
```

```bash
./scripts/mqtt_sim.sh
```

That starts the `mqtt-sim` container (`services/mqtt_simulator/publish.py`) and assigns its topics as **simulated** measurements. Habitat sensors and the overview environment card then update from the live stream: publisher → Mosquitto → API bridge → stored readings.

Stop it with `.\scripts\mqtt_sim.ps1 down`. Logs: `.\scripts\mqtt_sim.ps1 logs`.

The same script can run on the host instead of in Docker:

```bash
python scripts/mqtt_demo_sensors.py --host localhost
```

## 4. Assign

Each topic appears under **Topics seen**. Press **Assign**, then set:

| Field | What to enter |
|---|---|
| **Measures** | The metric. Habitat metrics are cabin CO₂, temperature, humidity, pressure and radiation dose rate. Person metrics also need a crew member. |
| **JSON field** | Leave blank for a plain number; otherwise the key, for example `t` or `data.co2` |
| **Convert** | A preset, for example *CO₂ ppm → mmHg* or *hPa → kPa*. A live preview shows the converted value. |
| **Data** | *real sensor* or *simulated*; the label follows the data everywhere |
| **Store every** | Saves one reading per N seconds, so fast sensors don't flood the database |

Assigned readings flow into the dashboard, alerts and models like any other measurement.

## Topic wildcards

- `+` matches one level: `habitat/+/co2` covers every module's CO₂.
- `#` matches everything below a level: `habitat/#`.
