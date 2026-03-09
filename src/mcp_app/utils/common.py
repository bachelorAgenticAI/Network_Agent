import urllib.parse

import httpx

HEADERS = {
    "Accept": "application/yang-data+json",
    "Content-Type": "application/yang-data+json",
}


# Return a preconfigured Async HTTP client for a router
def get_client(router):
    return httpx.AsyncClient(
        verify=False,
        auth=(router.user, router.password),
        headers=HEADERS,
        timeout=10.0,
    )


# Encode special characters for RESTCONF URLs (e.g., interface names)
def encode_intf(name: str) -> str:
    return urllib.parse.quote(name, safe="")
