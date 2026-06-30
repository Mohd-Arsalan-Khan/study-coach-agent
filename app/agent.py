# ruff: noqa
# Copyright 2026 Google LLC

import os
from dotenv import load_dotenv
load_dotenv()
from pydantic import BaseModel, Field
import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter

from google.adk.workflow import Workflow, node
from google.adk.events.event import Event
from google.adk.agents.context import Context
from google.adk.apps import App, ResumabilityConfig
from google.genai import types
from google.adk.events.request_input import RequestInput
from openai import OpenAI
import json
from typing import Any

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from mcp_server.notes_server import read_study_notes, list_available_notes, save_progress, load_progress

from app.security.context_resolver import ContextResolver
from app.security.sanitizer import Sanitizer, SecurityException

resolver = ContextResolver()

# --- Initialize OpenAI Client (NVIDIA NIM) ---
client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.environ.get("NVIDIA_API_KEY")
)
model = "meta/llama-3.1-8b-instruct"

# --- State Schema ---
class UserProfile(BaseModel):
    extracted_topics: list[str] = Field(default_factory=list)
    topic_scores: dict[str, float] = Field(default_factory=dict)
    weak_areas: list[str] = Field(default_factory=list)
    current_quiz_topics: list[str] = Field(default_factory=list)
    skip_ingest: bool = Field(default=False)
    original_text: str = Field(default="")

# --- Vector Store & Splitting ---
chroma_client = chromadb.Client()
collection = chroma_client.get_or_create_collection(name="study_notes")
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

def retrieve_context(query: str, n_results: int = 3) -> str:
    if collection.count() == 0:
        return "No relevant context found (collection is empty)."
    results = collection.query(query_texts=[query], n_results=n_results)
    if not results["documents"] or not results["documents"][0]:
        return "No relevant context found."
    return "\n---\n".join(results["documents"][0])

# --- I/O Schemas ---
class TopicStructure(BaseModel):
    topics: list[str] = Field(description="Main topics and subtopics extracted from the text")

class QuizQuestions(BaseModel):
    target_topics: list[str] = Field(description="The topics this quiz covers")
    questions: list[str] = Field(description="5 multiple choice questions")

class EvaluationResult(BaseModel):
    score: float = Field(description="Score on a 1-5 scale")
    feedback: str = Field(description="Detailed feedback on the answers")

class RevisionPlan(BaseModel):
    plan_details: str = Field(description="3-day personalized revision plan")

# --- Nodes ---

# 0. State Loader
@node(name="load_progress_state")
async def load_progress_state(ctx: Context, node_input: types.Content):
    try:
        progress = load_progress()
        if isinstance(progress, dict):
            ctx.state["topic_scores"] = progress.get("topic_scores", {})
            ctx.state["weak_areas"] = progress.get("weak_areas", [])
    except Exception:
        pass
        
    text = ""
    if node_input and node_input.parts:
        text = node_input.parts[0].text
        
    if "[CMD: START_QUIZ]" in text:
        topic = text.split("TOPIC: ")[1].strip() if "TOPIC: " in text else "General"
        ctx.state["extracted_topics"] = [topic]
        ctx.state["skip_ingest"] = True
    elif "[CMD: PLANNER]" in text:
        ctx.state["skip_ingest"] = True
        
    ctx.state["original_text"] = text
        
    return Event(output=node_input)

# 1. Ingestion Agent
@node(name="ingest_llm")
def ingest_llm(ctx: Context, node_input: types.Content):
    text = ""
    if node_input and node_input.parts:
        text = node_input.parts[0].text
        
    if "[CMD: START_QUIZ]" in text or "[CMD: PLANNER]" in text or ctx.state.get("skip_ingest"):
        return Event(output="")
        
    # Natively fetch notes instead of relying on tool calling loop
    available_notes = list_available_notes()
    all_notes_content = ""
    for note in available_notes:
        try:
            filename = os.path.basename(note)
            all_notes_content += f"\n--- {filename} ---\n{read_study_notes(note)}\n"
        except Exception:
            pass
            
    instruction = "You are the ingestion manager. The user has provided some study notes below. Output the full combined text of all notes."
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": instruction},
            {"role": "user", "content": f"Please process the following notes:\n\n{all_notes_content}"}
        ]
    )
    return Event(output=response.choices[0].message.content)

@node(name="chunk_and_embed")
def chunk_and_embed(ctx: Context, node_input: str):
    text = str(node_input)
    if not text or len(text) < 10:
        return Event(output={"text": ""})
        
    try:
        text = Sanitizer.sanitize_input(text)
    except SecurityException as e:
        return Event(output={"text": f"Security Error: {e}"})
        
    text = resolver.resolve(text)
    chunks = text_splitter.split_text(text)
    ids = [f"doc_{ctx.run_id}_{i}" for i in range(len(chunks))]
    metadatas = [{"source": "ingest_llm"} for _ in chunks]
    if chunks:
        collection.add(documents=chunks, metadatas=metadatas, ids=ids)
    
    return Event(output={"text": text})

# 2. Topic Extractor
@node(name="extract_llm")
def extract_llm(ctx: Context, node_input: dict):
    # chunk_and_embed returns a dict: {"text": text}
    text = node_input.get("text", "")
    if not text:
        return Event(output=TopicStructure(topics=[]))
        
    instruction = "Analyze the provided study notes. Extract the main topics and subtopics as a structured list."
    response = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": instruction},
            {"role": "user", "content": text}
        ],
        response_format=TopicStructure
    )
    return Event(output=response.choices[0].message.parsed)

@node(name="save_topics_to_state")
def save_topics_to_state(ctx: Context, node_input: TopicStructure):
    current_topics = set(ctx.state.get("extracted_topics", []))
    current_topics.update(node_input.topics)
    
    return Event(
        output={"topics": list(current_topics)},
        state={"extracted_topics": list(current_topics)}
    )

@node(name="router_node")
def router_node(ctx: Context, node_input: dict):
    text = ctx.state.get("original_text", "").lower()
    keywords = ["remind", "reminder", "schedule", "daily"]
    if any(k in text for k in keywords):
        return Event(output=node_input, branch="prepare_reminder")
    return Event(output=node_input, branch="prepare_quiz")

@node(name="prepare_reminder")
def prepare_reminder(ctx: Context, node_input: dict):
    return Event(output="Please confirm the user's reminder request nicely and say we saved it.")

@node(name="reminder_llm")
def reminder_llm(ctx: Context, node_input: str):
    instruction = "You are a friendly study coach. The user wants to set a reminder. Confirm it was saved."
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": instruction},
            {"role": "user", "content": str(node_input)}
        ]
    )
    return Event(output=response.choices[0].message.content)

# 3. Quiz Generator
@node(name="prepare_quiz")
def prepare_quiz(ctx: Context, node_input: dict):
    print("prepare_quiz: STARTING node")
    
    import concurrent.futures
    
    def _inner():
        topics = ctx.state.get("extracted_topics", [])
        scores = ctx.state.get("topic_scores", {})
        
        target_topics = []
        for t in topics:
            if t not in scores or scores[t] < 3:
                target_topics.append(t)
                
        if not target_topics:
            target_topics = topics[:3] if topics else ["General"]
            
        print("prepare_quiz: calling retrieve_context...")
        context = retrieve_context(" ".join(target_topics), n_results=5)
        print("prepare_quiz: retrieve_context completed")
        
        prompt = f"Target Topics: {target_topics}\nContext:\n{context}"
        print("prepare_quiz: calling resolver.resolve...")
        prompt = resolver.resolve(prompt)
        print("prepare_quiz: resolver.resolve completed")
        return Event(output=prompt, state={"current_quiz_topics": target_topics})

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_inner)
        try:
            result = future.result(timeout=30.0)
            print("prepare_quiz: ENDING node successfully")
            return result
        except concurrent.futures.TimeoutError:
            print("prepare_quiz: TIMEOUT ERROR - Hanging for 30s!")
            return Event(output="Timeout", state={"current_quiz_topics": ["General"]})

@node(name="quiz_llm")
def quiz_llm(ctx: Context, node_input: str):
    instruction = "Generate exactly 5 multiple choice questions covering the target topics provided. Include A,B,C,D options."
    response = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": instruction},
            {"role": "user", "content": str(node_input)}
        ],
        response_format=QuizQuestions
    )
    return Event(output=response.choices[0].message.parsed)

@node(name="ask_user_quiz", rerun_on_resume=True)
async def ask_user_quiz(ctx: Context, node_input: QuizQuestions):
    if not ctx.resume_inputs or "quiz_answers" not in ctx.resume_inputs:
        q_text = "\n\n".join(node_input.questions)
        msg = f"🧠 **Quiz Time!** Covering {node_input.target_topics}\n\n{q_text}\n\nPlease provide your answers:"
        yield RequestInput(interrupt_id="quiz_answers", message=msg)
        return
        
    user_answers = ctx.resume_inputs["quiz_answers"]
    yield Event(output={"quiz": node_input.model_dump(), "answers": user_answers})

# 4. Answer Evaluator
@node(name="prepare_eval")
def prepare_eval(ctx: Context, node_input: dict):
    quiz = node_input["quiz"]
    answers = node_input["answers"]
    target_topics = ctx.state.get("current_quiz_topics", ["General"])
    context = retrieve_context(" ".join(target_topics), n_results=5)
    
    prompt = f"Context:\n{context}\n\nQuiz Questions:\n{json.dumps(quiz)}\n\nUser Answers:\n{answers}"
    prompt = resolver.resolve(prompt)
    return Event(output=prompt)

@node(name="evaluator_llm")
def evaluator_llm(ctx: Context, node_input: str):
    instruction = """You are an expert LLM-as-judge. Compare the user's answers to the quiz questions using the provided context.
Score the performance strictly on a 1 to 5 scale (1=Poor, 5=Excellent). Provide detailed feedback."""
    response = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": instruction},
            {"role": "user", "content": str(node_input)}
        ],
        response_format=EvaluationResult
    )
    return Event(output=response.choices[0].message.parsed)


@node(name="save_eval_to_state")
async def save_eval_to_state(ctx: Context, node_input: EvaluationResult):
    target_topics = ctx.state.get("current_quiz_topics", ["General"])
    
    scores = dict(ctx.state.get("topic_scores", {}))
    for t in target_topics:
        scores[t] = (scores.get(t, node_input.score) + node_input.score) / 2
        
    weak_areas = [t for t, s in scores.items() if s < 3]
    
    try:
        save_progress(scores, weak_areas)
    except Exception:
        pass
    
    return Event(
        output={"score": node_input.score, "feedback": node_input.feedback},
        state={"topic_scores": scores, "weak_areas": weak_areas}
    )

# 5. Revision Planner
@node(name="prepare_planner")
def prepare_planner(ctx: Context, node_input: dict):
    weak_areas = ctx.state.get("weak_areas", [])
    prompt = f"Weak Areas: {weak_areas}\nRecent Feedback: {node_input['feedback']}"
    prompt = resolver.resolve(prompt)
    return Event(output=prompt)

@node(name="planner_llm")
def planner_llm(ctx: Context, node_input: str):
    instruction = "Generate a personalized 3-day revision plan allocating time to the provided weak areas."
    print("Starting planner_llm API call...")
    try:
        response = client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": str(node_input)}
            ],
            response_format=RevisionPlan,
            timeout=30.0
        )
        print("planner_llm API call completed successfully.")
        return Event(output=response.choices[0].message.parsed)
    except Exception as e:
        print(f"planner_llm API call failed: {e}")
        return Event(output=RevisionPlan(plan_details=f"Failed to generate plan: {e}"))

@node(name="format_final_output")
def format_final_output(ctx: Context, node_input: RevisionPlan):
    weak = ctx.state.get("weak_areas", [])
    scores = ctx.state.get("topic_scores", {})
    return Event(output=f"### Your 3-Day Revision Plan\n{node_input.plan_details}\n\n**Current Weak Areas**: {weak}\n**Topic Scores**: {scores}")

@node(name="end_workflow")
def end_workflow(ctx: Context, node_input: Any):
    return Event(output=node_input)

# --- Graph Edges ---
edges = [
    # 0. Load state
    ('START', load_progress_state),
    
    # 1. Ingest
    (load_progress_state, ingest_llm),
    (ingest_llm, chunk_and_embed),
    
    # 2. Extract topics
    (chunk_and_embed, extract_llm),
    (extract_llm, save_topics_to_state),
    (save_topics_to_state, router_node),
    
    # Reminder Branch
    (router_node, prepare_reminder),
    (prepare_reminder, reminder_llm),
    (reminder_llm, end_workflow),
    
    # 3. Quiz 
    (router_node, prepare_quiz),
    (prepare_quiz, quiz_llm),
    (quiz_llm, ask_user_quiz),  # HITL Pause
    
    # 4. Evaluate
    (ask_user_quiz, prepare_eval),
    (prepare_eval, evaluator_llm),
    (evaluator_llm, save_eval_to_state),
    
    # 5. Plan
    (save_eval_to_state, prepare_planner),
    (prepare_planner, planner_llm),
    
    # End
    (planner_llm, format_final_output),
    (format_final_output, end_workflow)
]

root_agent = Workflow(
    name="study_coach",
    edges=edges,
    state_schema=UserProfile,
    input_schema=types.Content,
)

app = App(
    root_agent=root_agent,
    name="app",
    resumability_config=ResumabilityConfig(enabled=True)
)
