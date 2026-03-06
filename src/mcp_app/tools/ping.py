import logging

import asyncssh
from utils.routers import get_router


async def ping(router_name: str, destination: str, source: str = None) -> dict:
    router = get_router(router_name)
    logging.info(f"Pinging {destination} from {router.name} ({router.host})")

    cmd = f"ping {destination}"
    if source:
        cmd += f" source {source}"

    try:
        async with asyncssh.connect(
            router.host,
            username=router.user,
            password=router.password,
            known_hosts=None,
        ) as conn:
            result = await conn.run(cmd, check=True)
            return {"output": result.stdout.strip()}
    except Exception as e:
        logging.warning(f"Ping failed on {router.name}: {e}")
        return {"error": str(e)}


async def traceroute(router_name: str, destination: str) -> dict:
    router = get_router(router_name)
    logging.info(f"Tracerouting to {destination} from {router.name} ({router.host})")

    cmd = f"traceroute {destination}"

    try:
        async with asyncssh.connect(
            router.host,
            username=router.user,
            password=router.password,
            known_hosts=None,
        ) as conn:
            result = await conn.run(cmd, check=True)
            return {"output": result.stdout.strip()}
    except Exception as e:
        logging.warning(f"Traceroute failed on {router.name}: {e}")
        return {"error": str(e)}


def register_ping_tools(mcp):
    mcp.tool(
        description=(
            "Run ping from the router CLI to validate end-to-end reachability/latency."
        )
    )(ping)
    mcp.tool(
        description=(
            "Run traceroute from the router CLI to identify forwarding path and hop-by-hop loss."
        )
    )(traceroute)
