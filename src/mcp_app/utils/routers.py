class Router:
    def __init__(self, name: str, host: str, user: str, password: str):
        self.name = name
        self.host = host
        self.user = user
        self.password = password


# Predefined set of available routers
ROUTERS = {
    "router1": Router(name="R1", host="192.168.0.1", user="restconf", password="pswd"),
    "router2": Router(name="R2", host="172.16.0.1", user="restconf", password="pswd"),
    "router3": Router(name="R3", host="203.0.113.1", user="restconf", password="pswd"),
}


# Fetch a Router object by its internal name
def get_router(name: str) -> Router:

    return ROUTERS[name.lower()]
