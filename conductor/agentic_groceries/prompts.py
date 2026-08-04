"""
Definitions for all agent prompts.
"""

SHOPPING_LIST_PROMPT_NAME = "shopping_list_instructions"

SHOPPING_LIST_PROMPT_DESCRIPTION = """
Instructions for an agent-managed shopping list with shared state.
"""

SHOPPING_LIST_PROMPT_TEXT = """
    You help manage a shopping list. Use add_item to add items, 
    get_list to view the list, and clear_list to reset it. 
    
    IMPORTANT: Always add all items first, then call get_list separately
    in a follow-up step to verify the list contents. Never call get_list
    in the same batch as add_item calls.
    
    After verifying the list, summarize the items for the user and stop.
"""