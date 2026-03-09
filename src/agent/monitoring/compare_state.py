import asyncio
import json
import logging
from pathlib import Path

from agent.monitoring.get_quick_state import collect_all_devices_interfaces

MEMORY_DIR = Path(__file__).resolve().parent.parent / "memory"
STATE_FILE = MEMORY_DIR / "last_state.json"
ALERT_FILE = MEMORY_DIR / "alerts.json"
INCIDENT_FILE = MEMORY_DIR / "incidents.json"
CUSTOM_ALERT_FILE = MEMORY_DIR / "custom_alerts.json"  # <--- manual test

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


def load_custom_alerts():
    """Load and clear custom alerts for test cases."""
    if not CUSTOM_ALERT_FILE.exists():
        return []
    alerts = load_json(CUSTOM_ALERT_FILE, default=[])
    CUSTOM_ALERT_FILE.unlink()  # remove after loading
    return alerts


async def compare():
    # Load custom alerts first
    custom_alerts = load_custom_alerts()

    # If custom alerts exist → use only them
    if custom_alerts:
        save_json(ALERT_FILE, custom_alerts)
        print_alerts(custom_alerts)
        return custom_alerts

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
            incident = updated_incidents.get(key)

            # ===== New Interface Detection =====
            if not old_intf:
                alerts.append(
                    {
                        "type": "interface_new",
                        "device": device,
                        "interface": name,
                        "new_oper_state": new_intf.get("oper_state"),
                    }
                )
                updated_incidents[key] = {"active": True}
                continue

            old_oper = old_intf.get("oper_state")
            new_oper = new_intf.get("oper_state")

            # ===== Oper State Change =====
            if old_oper != new_oper:
                if incident:
                    updated_incidents.pop(key, None)
                else:
                    alerts.append(
                        {
                            "type": "oper_state_change",
                            "device": device,
                            "interface": name,
                            "old_state": old_oper,
                            "new_state": new_oper,
                        }
                    )
                    updated_incidents[key] = {"active": True}

            # ===== Counter Thresholds =====
            for metric, threshold in [
                ("input_errors", ERROR_THRESHOLD),
                ("output_errors", ERROR_THRESHOLD),
                ("drops", DROP_THRESHOLD),
            ]:
                old_val = old_intf.get(metric) or 0
                new_val = new_intf.get(metric) or 0
                delta = max(0, new_val - old_val)
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

    header = f"{'DEVICE':20} {'INTERFACE':20} {'TYPE':25} DETAILS"
    print(header)
    print("-" * len(header))

    for a in alerts:
        device = a.get("device", "-")
        interface = a.get("interface", "-")
        alert_type = a.get("type", "-")
        details = ", ".join(
            f"{k}={v}" for k, v in a.items() if k not in ("device", "interface", "type")
        )
        print(f"{device:20} {interface:20} {alert_type:25} {details}")

    print()


if __name__ == "__main__":
    alerts = asyncio.run(compare())
    if alerts:
        logging.warning(f"{len(alerts)} alerts detected")
    else:
        logging.info("No alerts detected")
