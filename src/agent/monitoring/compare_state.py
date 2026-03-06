import asyncio
import json
import logging
from pathlib import Path

from agent.monitoring.get_quick_state import collect_all_devices_interfaces

MEMORY_DIR = Path(__file__).resolve().parent.parent / "memory"
STATE_FILE = MEMORY_DIR / "last_state.json"
ALERT_FILE = MEMORY_DIR / "alerts.json"
INCIDENT_FILE = MEMORY_DIR / "incidents.json"

ERROR_THRESHOLD = 50
DROP_THRESHOLD = 50


def load_json(file_path, default=None):
    if not file_path.exists():
        return default
    with open(file_path) as f:
        return json.load(f)


def save_json(file_path, data):
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)


def build_map(state):
    devices = {}
    for device in state.get("devices", []):
        interfaces = {i["name"]: i for i in device.get("interfaces", [])}
        devices[device["device"]] = interfaces
    return devices


async def compare():
    old_state = load_json(STATE_FILE, default={"devices": []})
    new_state = await collect_all_devices_interfaces()

    alerts = []

    old_map = build_map(old_state)
    new_map = build_map(new_state)
    incidents = load_json(INCIDENT_FILE, default={})
    updated_incidents = incidents.copy()

    for device, interfaces in new_map.items():
        old_interfaces = old_map.get(device, {})

        for name, new_intf in interfaces.items():
            old_intf = old_interfaces.get(name)

            key = f"{device}:{name}"
            new_state_val = new_intf.get("oper_state")
            incident = incidents.get(key)

            # ===== New Interface Detection =====
            if not old_intf:
                alerts.append(
                    {
                        "type": "interface_new",
                        "device": device,
                        "interface": name,
                        "new_state": new_state_val,
                    }
                )
                continue

            old_state_val = old_intf.get("oper_state")

            # ===== Interface Down Detection =====
            if old_state_val == "up" and new_state_val == "down":
                if not incident or not incident.get("active"):
                    alerts.append(
                        {
                            "type": "interface_down",
                            "device": device,
                            "interface": name,
                            "old_state": old_state_val,
                            "new_state": new_state_val,
                        }
                    )
                    updated_incidents[key] = {"active": True}

            # ===== Interface Up =====
            elif old_state_val == "down" and new_state_val == "up":
                # Recovery: clear incident, no alert
                if incident and incident.get("active"):
                    updated_incidents[key]["active"] = False
                else:
                    # Unexpected up event
                    alerts.append(
                        {
                            "type": "interface_up",
                            "device": device,
                            "interface": name,
                            "old_state": old_state_val,
                            "new_state": new_state_val,
                        }
                    )

            # ===== Counter Thresholds =====
            for metric, threshold in [
                ("input_errors", ERROR_THRESHOLD),
                ("output_errors", ERROR_THRESHOLD),
                ("drops", DROP_THRESHOLD),
            ]:
                old_val = old_intf.get(metric, 0) or 0
                new_val = new_intf.get(metric, 0) or 0

                if new_val >= old_val:
                    delta = new_val - old_val
                    if delta >= threshold:
                        alerts.append(
                            {
                                "type": "threshold_exceeded",
                                "device": device,
                                "interface": name,
                                "metric": metric,
                                "errors_since_last_check": delta,
                            }
                        )

    # Save current state and incidents
    save_json(STATE_FILE, new_state)
    save_json(INCIDENT_FILE, updated_incidents)
    save_json(ALERT_FILE, alerts)

    print_alerts(alerts)
    return alerts


def print_alerts(alerts):
    if not alerts:
        print("\n=== ALERT SUMMARY ===")
        print("No alerts detected\n")
        return

    print("\n=== ALERT SUMMARY ===\n")

    header = f"{'DEVICE':20} {'INTERFACE':20} {'TYPE':20} DETAILS"
    print(header)
    print("-" * len(header))

    for a in alerts:
        device = a.get("device", "-")
        interface = a.get("interface", "-")
        alert_type = a.get("type", "-")

        details = ", ".join(
            f"{k}={v}" for k, v in a.items() if k not in ("device", "interface", "type")
        )

        print(f"{device:20} {interface:20} {alert_type:20} {details}")

    print()


# Only used for testing - in production this script would be called by compare() from agent.py
if __name__ == "__main__":
    alerts = asyncio.run(compare())
    if alerts:
        logging.warning(f"{len(alerts)} alerts detected")
    else:
        logging.info("No alerts detected")
