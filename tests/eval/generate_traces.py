import asyncio
import json
import os
import sys
import time

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from app.agent import app
from google.genai import types

async def run_with_retry(runner, new_message, user_id, session_id):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            events = []
            async for event in runner.run_async(new_message=new_message, user_id=user_id, session_id=session_id):
                events.append(event)
            return events
        except Exception as e:
            if ("503" in str(e) or "429" in str(e)) and attempt < max_retries - 1:
                print(f"API Error ({e}) during generation, retrying in {5 * (attempt + 1)}s...")
                await asyncio.sleep(5 * (attempt + 1))
            else:
                raise e

async def generate():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    dataset_path = os.path.join(base_dir, "tests", "eval", "datasets", "basic-dataset.json")
    out_dir = os.path.join(base_dir, "artifacts", "traces")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "generated_traces.json")
    notes_dir = os.path.join(base_dir, "notes")
    os.makedirs(notes_dir, exist_ok=True)
    
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        eval_cases = data.get("eval_cases", [])
        
    traces = []
    print(f"Generating traces for {len(eval_cases)} scenarios...")
    for idx, case in enumerate(eval_cases):
        print(f"Running scenario {idx + 1}: {case.get('id')}")
        try:
            from google.adk.runners import Runner
            from google.adk.sessions import InMemorySessionService
            
            # Setup input files for the scenario
            # Clear old notes
            for file_name in os.listdir(notes_dir):
                if file_name.endswith(".txt") or file_name.endswith(".docx"):
                    os.remove(os.path.join(notes_dir, file_name))
            
            # Write new notes
            case_input = case.get("input", {})
            if "text" in case_input:
                with open(os.path.join(notes_dir, f"{case.get('id')}_notes.txt"), "w", encoding="utf-8") as f:
                    f.write(case_input["text"])
            
            # Reset progress
            progress_path = os.path.join(base_dir, "progress.json")
            if os.path.exists(progress_path):
                os.remove(progress_path)
            
            session_service = InMemorySessionService()
            runner = Runner(agent=app.root_agent, session_service=session_service, app_name="eval")
            session = session_service.create_session_sync(user_id="test_user", app_name="eval")
            
            prompt_dict = case.get("prompt", {})
            parts = [types.Part.from_text(text=p["text"]) for p in prompt_dict.get("parts", [])]
            new_message = types.Content(role=prompt_dict.get("role", "user"), parts=parts)
            
            all_events = []
            
            # Run initial prompt
            events = await run_with_retry(runner, new_message, "test_user", session.id)
            all_events.extend(events)
            
            # Handle human in the loop
            if all_events and type(all_events[-1]).__name__ == "RequestInput":
                answers = case_input.get("answers", "I don't know")
                resume_msg = types.Content(role="user", parts=[types.Part.from_text(text=str(answers))])
                print(f"  -> Agent requested input. Providing answers: {answers}")
                resume_events = await run_with_retry(runner, resume_msg, "test_user", session.id)
                all_events.extend(resume_events)
                
            final_event = all_events[-1] if all_events else None
            
            trace_events = []
            for ev in all_events:
                trace_events.append({
                    "type": type(ev).__name__,
                    "output": str(getattr(ev, "output", getattr(ev, "message", None)))
                })
            
            trace = {
                "id": case.get("id"),
                "prompt": case.get("prompt"),
                "response": str(getattr(final_event, "output", "None")) if final_event else "None",
                "agent_data": {
                    "state": getattr(final_event, "state", {}),
                    "events": trace_events
                }
            }
            traces.append(trace)
        except Exception as e:
            print(f"Failed {case.get('id')}: {e}")
            traces.append({
                "id": case.get("id"),
                "prompt": case.get("prompt"),
                "response": f"Error: {e}",
                "agent_data": {}
            })
            
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"eval_cases": traces}, f, indent=4)
        
    print(f"Saved traces to {out_path}")

if __name__ == "__main__":
    asyncio.run(generate())
