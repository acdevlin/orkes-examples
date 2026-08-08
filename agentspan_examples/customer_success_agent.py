
# Required import to avoid pickling error from @tool in the current SDK.
# Should be resolved with this pull: https://github.com/conductor-oss/python-sdk/pull/414
import multiprocessing
multiprocessing.set_start_method("fork", force=True)

import logging
logging.disable(logging.INFO)

import os
import google.genai as genai
from conductor.ai.agents import Agent, AgentRuntime, tool

_llm = genai.Client()


def summarize_result(tool_name: str, result: dict) -> str:
  prompts = {
    "get_hubspot_data": "You just retrieved HubSpot CRM data for a customer. Summarize what you found in 1-2 sentences. If data is missing or empty, say so clearly.",
    "get_slack_data":   "You just retrieved Slack channel messages for a customer. Summarize what you found — key issues, sentiment, urgency — in 1-2 sentences. If there are no messages, say so clearly.",
  }
  system = prompts.get(tool_name, "Summarize what you found in 1-2 sentences.")
  msg = _llm.interactions.create(
    model="gemini-3.1-flash-lite",
    system_instruction=system,
    input=f"Data: {result}",
  )
  return msg.output_text.strip()

def summarize_intervention(context: dict, reason: str, recommended_action: str) -> str:
  msg = _llm.interactions.create(
    model="gemini-3.1-flash-lite",
    system_instruction=(
      "You are briefing a human agent who must decide whether to intervene in a customer support case. "
      "Write a concise summary covering: who the customer is, what their issue is, what actions the agent has already taken, "
      "and why intervention is being requested. Be factual and direct."
    ),
    input=(
      f"Customer data: {context}\n\n"
      f"Reason for intervention: {reason}\n"
      f"Recommended action: {recommended_action}"
    ),
  )
  return msg.output_text.strip()

# ---------------------------------------------------------------------------
# Tools for the agent
# ---------------------------------------------------------------------------
@tool
def get_hubspot_data(customer_id: str) -> dict:
  """Get account details for a customer from HubSpot.
  Returns plan tier, contract value, lifecycle stage, and account owner.
  """

  return {
    "customer_id": customer_id,
    "company": "Sekro",
    "contract_value": 48000,
    "lifecycle_stage": "customer",
    "health_score": 62,
    "account_owner": "jane@yourcompany.com",
  }

@tool
def get_slack_data(customer_id: str) -> dict:
  """Get the 100 most recent Slack messages from the customer's shared channel."""
  return {
    "customer_id": customer_id,
    "channel": "#sekro",
    "messages": [
      {"user": "bob@sekro.com", "text": "Hey, our exports have been failing since Tuesday", "ts": "2025-06-10T09:12:00Z"},
      {"user": "jane@yourcompany.com", "text": "Looking into it now!", "ts": "2025-06-10T09:15:00Z"},
      {"user": "bob@asekro.com", "text": "Still broken — our CFO is asking questions", "ts": "2025-06-11T14:03:00Z"},
      ],
  }

@tool
def open_zendesk_ticket(subject: str, description: str, priority: str = "high") -> dict:
  """Open a support ticket in Zendesk.
  Call this AT MOST ONCE. If the issue needs another ticket, request intervention instead.
  """

  return {
    "ticket_id": "ZD-99182",
    "subject": subject,
    "priority": priority,
    "status": "open",
    "url": "https://support.yourcompany.zendesk.com/tickets/99182",
  }

@tool(approval_required=True)
def request_intervention(reason: str, recommended_action: str) -> dict:
  """Request a human agent to intervene.
  Use this when confidence is low, when the issue is high-stakes, or when no available action seems right.
  """
  return {"status": "intervention_requested", "reason": reason, "recommended_action": recommended_action}

# ---------------------------------------------------------------------------
# Agent prompt
# ---------------------------------------------------------------------------
INSTRUCTIONS= """
You are a customer success agent for a SaaS company. 

Your goal is to keep the customer happy. 

You wull be given a customer ID and a description of their issue. Work through the issue step by step:
1. Get the customer's Hubspot data to understand their tier and importance
2. Check their Slack history to understand the full context 
3. Based on what you learn, either open a Zendesk ticket or request human intervention

Rules:
- Open a Zendesk ticket AT MOST ONCE. If you already opened one, request intervention instead.
- If you have low confidence at any point, request intervention immediately.
- High-value customers (contracts > $25k) should have intervention requested if the issue is unresolved after 2 steps.
"""

# ---------------------------------------------------------------------------
# Define the Agent
# ---------------------------------------------------------------------------
agent = Agent(
  name="CustomerSuccessAgent",
  model="google_gemini/gemini-3.1-flash-lite",
  tools=[get_hubspot_data, get_slack_data, open_zendesk_ticket, request_intervention],
  instructions=INSTRUCTIONS,
  max_turns=5
)

# ---------------------------------------------------------------------------
# Run the Agent
# ---------------------------------------------------------------------------
if __name__ == "__main__":
  import sys
  if len(sys.argv) > 1:
    user_input = " ".join(sys.argv[1:])
  else:
    user_input = input("Describe the customer issue: ")

  print("\n" + "=" * 60)
  print("  CUSTOMER SUCCESS AGENT")
  print(f"  Investigating: {user_input}")
  print("=" * 60 + "\n")

  with AgentRuntime() as runtime:
    handle = runtime.start(agent, user_input)
    print(f"Execution ID: {handle.execution_id}\n")

    step = 0
    escalating = False
    collected_context = {}

    def handle_event(event):
      global step, escalating, collected_context
      if event.type == "tool_call":
        if event.tool_name == "request_intervention":
          escalating = True
          return  # printed by main thread at approval time
        step += 1
        tool_labels = {
          "get_hubspot_data":    "Looking up customer in HubSpot",
          "get_slack_data":      "Reading Slack channel history",
          "open_zendesk_ticket": "Opening Zendesk support ticket",
        }
        label = tool_labels.get(event.tool_name, event.tool_name)
        print(f"\n  STEP {step}: {label}", flush=True)

      elif event.type == "tool_result":
        if event.tool_name == "get_hubspot_data":
          r = event.result or {}
          collected_context["hubspot"] = r
          print(f"  Company:        {r.get('company', '-')}")
          print(f"  Plan:           {r.get('plan', '-')}")
          print(f"  Contract value: ${r.get('contract_value', '-'):,}")
          print(f"  Health score:   {r.get('health_score', '-')}")
          print(f"  Account owner:  {r.get('account_owner', '-')}")
          summary = summarize_result("get_hubspot_data", r)
          print(f"\n  Here's what I found: {summary}\n", flush=True)

        elif event.tool_name == "get_slack_data":
          r = event.result or {}
          collected_context["slack"] = r
          messages = r.get("messages", [])
          print(f"  Channel: {r.get('channel', '-')} — {len(messages)} messages")
          for m in messages:
            print(f"    {m.get('user', '?')}: {m.get('text', '')}")
          summary = summarize_result("get_slack_data", r)
          print(f"\n  Here's what I found: {summary}\n", flush=True)

        elif event.tool_name == "open_zendesk_ticket":
          r = event.result or {}
          collected_context["zendesk_ticket"] = r
          print(f"  Ticket ID: {r.get('ticket_id', '-')}")
          print(f"  Priority:  {r.get('priority', '-')}")
          print(f"  URL:       {r.get('url', '-')}", flush=True)

      elif event.type == "done":
        output = event.output
        result_text = output.get("result", output) if isinstance(output, dict) else output
        print("\n" + "=" * 60)
        print("  AGENT SUMMARY")
        print("=" * 60)
        print(f"\n{result_text}\n", flush=True)

    import threading
    import time
    import os
    import tty as tty_lib
    import termios

    def read_char():
      """Read a single keypress directly from the terminal.

      We open /dev/tty directly instead of using input() because the agent's
      stream is printing on a background thread at the same time. input() would
      conflict with that output. Reading raw from /dev/tty lets us capture one
      keypress cleanly without interfering with the stream.
      """
      fd = os.open("/dev/tty", os.O_RDWR)
      old = termios.tcgetattr(fd)  # save current terminal settings so we can restore them
      try:
        tty_lib.setraw(fd)                                    # disable line buffering — don't wait for Enter
        termios.tcflush(fd, termios.TCIFLUSH)                 # discard any buffered input before reading
        ch = os.read(fd, 1).decode("utf-8", errors="replace") # read exactly one keypress
      finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)  # restore original terminal settings
        os.close(fd)
      return ch

    # Two events used to coordinate between the main thread and the stream thread:
    # - pause_printing: set when we need the stream thread to stop printing (during approval prompt)
    # - stream_done: set when the stream has finished, so the main thread knows to stop polling
    pause_printing = threading.Event()
    stream_done = threading.Event()

    def run_stream():
      # Consume agent events on a background thread so the main thread stays free
      # to poll for human approval at the same time.
      for event in handle.stream():
        if not pause_printing.is_set():  # skip printing while the approval prompt is shown
          handle_event(event)
      stream_done.set()  # signal the main thread that the stream has ended

    # Start the stream thread as a daemon so it exits automatically if the main thread exits
    t = threading.Thread(target=run_stream, daemon=True)
    t.start()

    # Main thread polls every 2 seconds to check if the agent is waiting for human approval.
    # This runs concurrently with the stream thread printing agent progress.
    while not stream_done.is_set():
      time.sleep(2)
      status = handle.get_status()
      if status.is_waiting:
        pause_printing.set()           # tell the stream thread to stop printing
        time.sleep(0.2)                # brief wait to let the stream thread finish its current print
        pt = status.pending_tool or {}
        args = pt.get("args") or pt  # args may be nested or flat
        if escalating:
          step += 1
          print(f"\n  STEP {step}: Requesting human intervention")
        print("\n" + "=" * 60)
        print("  HUMAN APPROVAL REQUIRED")
        print("=" * 60)
        reason = args.get("reason", "")
        recommended_action = args.get("recommended_action", "")
        print(f"\n  Generating situation summary...", flush=True)
        brief = summarize_intervention(collected_context, reason, recommended_action)
        print(f"\n{brief}\n")
        print("=" * 60)
        print("\n  Mark as resolved? (y/n): ", end="", flush=True)
        answer = read_char().lower()
        print(answer)
        if answer == "y":
          handle.approve()
          print("\n  Marked as resolved.\n")
          pause_printing.clear()  # resume the stream thread so it can print remaining events
        else:
          handle.reject("Intervention not approved")
          print("\n  Intervention rejected.\n")
          result = handle.join()
          output = result.output or {}
          result_text = output.get("result", output) if isinstance(output, dict) else output
          print("\n" + "=" * 60)
          print("  AGENT SUMMARY")
          print("=" * 60)
          if result_text:
            print(f"\n{result_text}\n")
          else:
            print("\n  Intervention was not approved. No further action was taken.\n")
        break

    t.join(timeout=120)  # wait for the stream thread to finish before exiting