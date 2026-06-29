import asyncio
import os
import sys

from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel

# Ensure we can import from app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from google.genai import types
from google.adk.runners import Runner
from app.agent import app as adk_app
from google.adk.sessions import DatabaseSessionService
from mcp_server.notes_server import load_progress

app = FastAPI(title="Study Coach Ambient API")

# Initialize ADK Runner for asynchronous execution
runner = Runner(
    agent=adk_app.root_agent,
    session_service=DatabaseSessionService(db_url="sqlite+aiosqlite:///e:/Projects/study-coach-agent/.agents/sessions.db"),
    app_name=adk_app.name,
)

class PubSubEvent(BaseModel):
    student_id: str
    action: str
    topic: str = ""

@app.post("/trigger/pubsub")
async def trigger_pubsub(event: PubSubEvent, background_tasks: BackgroundTasks):
    async def run_agent():
        session_id = f"session-{event.student_id}"
        
        if event.action == "start_quiz":
            prompt = f"[CMD: START_QUIZ] TOPIC: {event.topic}"
        else:
            prompt = event.action

        new_message = types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
        
        try:
            async for event_output in runner.run_async(
                new_message=new_message,
                user_id=event.student_id,
                session_id=session_id
            ):
                pass
            print(f"[{event.student_id}] Pub/Sub workflow triggered successfully.")
        except Exception as e:
            print(f"Error processing pubsub event: {e}")
            
    background_tasks.add_task(run_agent)
    return {"status": "Event received and processing in background"}

class WebhookEvent(BaseModel):
    student_id: str
    quiz_id: str
    score: float

@app.post("/webhook/progress")
async def progress_webhook(event: WebhookEvent, background_tasks: BackgroundTasks):
    async def run_planner():
        session_id = f"session-{event.student_id}"
        prompt = f"[CMD: PLANNER] I completed quiz {event.quiz_id} with score {event.score}. Update plan."
        new_message = types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
        
        try:
            async for event_output in runner.run_async(
                new_message=new_message,
                user_id=event.student_id,
                session_id=session_id
            ):
                pass
            print(f"[{event.student_id}] Webhook workflow updated plan.")
        except Exception as e:
            print(f"Error processing webhook event: {e}")
            
    background_tasks.add_task(run_planner)
    return {"status": "Webhook received"}

async def daily_reminder_task():
    while True:
        # For testing, we run every 60 seconds. In production this would be 24 * 3600
        await asyncio.sleep(60)  
        student_id = "test-student"
        session_id = f"session-{student_id}"
        
        progress = load_progress()
        if isinstance(progress, dict):
            weak = progress.get("weak_areas", [])
            if weak:
                prompt = f"[CMD: PLANNER] Daily reminder: generate revision plan for weak areas {weak}."
                new_message = types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
                try:
                    async for _ in runner.run_async(
                        new_message=new_message,
                        user_id=student_id,
                        session_id=session_id
                    ):
                        pass
                    print(f"[{student_id}] Sent daily revision plan.")
                except Exception as e:
                    print(f"Failed daily reminder: {e}")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(daily_reminder_task())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
