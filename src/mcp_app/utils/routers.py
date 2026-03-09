class Router:
    def __init__(self, name: str, host: str, user: str, password: str):
        self.name = name
        self.host = host
        self.user = user
        self.password = password


# Predefined set of available routers
ROUTERS = {
    "router1": Router(name="Rango", host="192.168.50.1", user="restconf", password="pswd"),
    "router2": Router(name="Django", host="192.168.50.2", user="restconf", password="pswd"),
}


# Fetch a Router object by its internal name
def get_router(name: str) -> Router:

    return ROUTERS[name.lower()]
