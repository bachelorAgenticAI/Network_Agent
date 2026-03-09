"""Collect a lightweight snapshot of interface health from all configured routers."""

import logging
from typing import Any

from mcp_app.tools.device_info import get_running_config
from mcp_app.tools.interface_router import get_interface_status
from mcp_app.utils.routers import ROUTERS


# Build one normalized state payload used by compare_state.py.
async def collect_all_devices_interfaces() -> dict[str, Any]:
    result: list[dict[str, Any]] = []

    for router_key in ROUTERS.keys():
        try:
            running_config = await get_running_config(router_key)

            if "error" in running_config:
                logging.warning(f"Skipping {router_key}: {running_config['error']}")
                continue

            hostname = running_config.get("hostname")
            interfaces_data = running_config.get("interfaces", {})

            device_interfaces: list[dict[str, Any]] = []

            # Expand interface groups from running config and enrich with live status.
            for intf_type, intf_entries in interfaces_data.items():
                if not isinstance(intf_entries, list):
                    continue

                for intf in intf_entries:
                    interface_name = f"{intf_type}{intf.get('name')}"
                    status = await get_interface_status(router_key, interface_name)

                    if "error" in status:
                        logging.warning(
                            f"Skipping {interface_name} on {router_key}: {status['error']}"
                        )
                        continue

                    device_interfaces.append(
                        {
                            "name": interface_name,
                            "admin_state": status.get("admin_state"),
                            "oper_state": status.get("oper_state"),
                            "input_errors": status.get("input_errors"),
                            "output_errors": status.get("output_errors"),
                            "drops": status.get("drops"),
                        }
                    )

            result.append(
                {
                    "device": hostname,
                    "interfaces": device_interfaces,
                }
            )

        except Exception as e:
            logging.warning(f"Failed processing router {router_key}: {e}")

    return {"devices": result}
