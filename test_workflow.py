from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from app.agent import root_agent

def run_test():
    session_service = InMemorySessionService()
    session = session_service.create_session_sync(user_id="test_user", app_name="test")
    runner = Runner(agent=root_agent, session_service=session_service, app_name="test")
    
    text = "Hello! I have uploaded my study notes about AI Agents, MCP protocols, and Google ADK. Please start by reading my notes and telling me what topics you found."
    message = types.Content(role="user", parts=[types.Part.from_text(text=text)])
    
    print(f"Sending message: {text}\n")
    events = list(runner.run(new_message=message, user_id="test_user", session_id=session.id))
    
    for event in events:
        if event.node_name:
            print(f"\n--- Node: {event.node_name} ---")
            print(event.output)

if __name__ == "__main__":
    run_test()
