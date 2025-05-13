
from universal_mcp.servers.server import SingleMCPServer
from universal_mcp.integrations import AgentRIntegration
from universal_mcp.stores.store import EnvironmentStore

from universal_mcp_google_calendar.app import GoogleCalendarApp

env_store = EnvironmentStore()
integration_instance = AgentRIntegration(name="google-calendar", store=env_store)
app_instance = GoogleCalendarApp(integration=integration_instance)

mcp = SingleMCPServer(
    app_instance=app_instance,
)

if __name__ == "__main__":
    mcp.run()


