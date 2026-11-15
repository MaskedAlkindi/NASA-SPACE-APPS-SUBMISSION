"""Server connectors: HEALTH-01's links to other servers and online information.

Separate code base from the backend on purpose. A connector is a small class that knows how to test a URL and fetch
a summary from it. The backend stores which connections an operator added (name, kind, URL) and calls these classes.
Add a connector by dropping a module into servers/connectors/ with a subclass of servers.base.Connector.
"""
