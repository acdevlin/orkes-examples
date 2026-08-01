from conductor.ai.agents import Agent, AgentRuntime
from conductor.client.configuration.configuration import Configuration
from conductor.client.orkes_clients import OrkesClients
from conductor.client.configuration.settings.authentication_settings import AuthenticationSettings

import os

agent = Agent(
    name="greeter",
    model=os.environ.get('CONDUCTOR_AGENT_LLM_MODEL', 'google_gemini/gemini-3.1-flash-lite'),
    instructions="You are a friendly assistant. Keep responses brief.",
)

config = Configuration(
  base_url=os.environ.get('CONDUCTOR_SERVER_URL', 'https://developer.orkescloud.com'),
  authentication_settings=AuthenticationSettings(
    key_id=os.environ.get('ORKES_API_KEY', None),
    key_secret=os.environ.get('ORKES_API_SECRET', None)
  )
)
clients = OrkesClients(configuration=config)

with AgentRuntime() as runtime:
    result = runtime.run(
      agent, 
      "Say hello and share a fun Python fact."
    )
    result.print_result()
    