import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))

STARTING_BALANCE = 20000.0
WORKFLOW_FILE = os.path.join(APP_DIR, 'workflow.jsonc')
WORKFLOW_NAME = 'agentic_stock_trader_autonomous'
WORKFLOW_VERSION = 1
WORKFLOW_INPUT_INSTRUCTIONS = 'purchase 22 shares of NVIDIA stock (NVDA)'

BALANCE_FILE = os.path.join(APP_DIR, 'balance.dat')
LOG_FILE = os.path.join(APP_DIR, 'actions.log')

AI_PROVIDER = 'OpenAI_Key'
AI_MODEL_NAME = 'gpt-4o-mini'

PROMPT_NAMES = {
    'instructions': 'stock_agent_instructions',
    'decider': 'stock_agent_decider',
}

PROMPT_DESCRIPTIONS = {
    'instructions': 'Trading agent instructions',
    'decider': 'Trading agent decision prompt',
}

MIN_QUANTITY = 1
MAX_QUANTITY = 50
ALL_PHRASES = ('', 'all', 'everything', 'all shares')
