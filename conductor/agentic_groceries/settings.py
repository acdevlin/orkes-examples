import os

# Integration name for OpenAI, already saved in your Orkes account.
INTEGRATION_NAME = "OpenAI_Key"
# Model name from LLM provider, already saved in your Orkes account.    
MODEL_NAME = "gpt-4o-mini"
# SDK agent format: integration/model
SDK_MODEL = f"{INTEGRATION_NAME}/{MODEL_NAME}"
# Server prompt format: integration:model
SERVER_MODELS = [f"{INTEGRATION_NAME}:{MODEL_NAME}"]     
# URL for the main Orkes server API.
SERVER_URL = "https://developer.orkescloud.com/api"

# Authentication key and secret for your Orkes account,
# already saved as environment variables.
CONDUCTOR_AUTH_KEY = os.environ.get("CONDUCTOR_AUTH_KEY", None)
CONDUCTOR_AUTH_SECRET = os.environ.get("CONDUCTOR_AUTH_SECRET", None)

# Maximum number of turns for the agent to take before stopping.
MAX_TURNS = 10
# Tool poll interval in milliseconds, used within an agentic runtime.
POLL_INTERVAL_MS = 100

# JSON file containing the overarching Conductor workflow for our agents.
WORKFLOW_FILE = "meal_and_grocery_planner_workflow_v1.json"
