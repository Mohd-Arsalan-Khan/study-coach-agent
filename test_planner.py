import os
import asyncio
from app.agent import planner_llm
from google.adk.agents.context import Context

def run_test():
    ctx = Context(run_id="test", state={"weak_areas": ["Physics", "AI"]})
    print("Testing planner_llm directly...")
    result = planner_llm(ctx, "Recent Feedback: Score 2/5 on physics.")
    print("Result:")
    print(result.output)

if __name__ == "__main__":
    run_test()
