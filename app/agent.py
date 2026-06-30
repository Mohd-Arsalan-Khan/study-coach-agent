# ruff: noqa
# Copyright 2026 Google LLC

import os
import google.auth
from pydantic import BaseModel, Field
import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter

from google.adk.workflow import Workflow, node
from google.adk.events.event import Event
from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.apps import App, ResumabilityConfig
from google.adk.models import Gemini
from google.genai import types
from google.adk.events.request_input import RequestInput

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from mcp_server.notes_server import read_study_notes, list_available_notes, save_progress, load_progress

try:
    _, project_id = google.auth.default()
    os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
except Exception:
    pass
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

from app.security.context_resolver import ContextResolver
from app.security.sanitizer import Sanitizer, SecurityException

resolver = ContextResolver()

# --- State Schema ---
class UserProfile(BaseModel):
    extracted_topics: list[str] = Field(default_factory=list)
    topic_scores: dict[str, float] = Field(default_factory=dict)
    weak_areas: list[str] = Field(default_factory=list)
    current_quiz_topics: list[str] = Field(default_factory=list)
    skip_ingest: bool = Field(default=False)

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
        
    return Event(output=node_input)

# 1. Ingestion Agent
ingest_llm = LlmAgent(
    name="ingest_llm",
    model="gemini-flash-latest",
    instruction="""You are the ingestion manager. Use 'list_available_notes' to find files.
Then use 'read_study_notes' to read them. Finally, output the full combined text of all notes.
CRITICAL: If the user prompt starts with [CMD: START_QUIZ] or [CMD: PLANNER], you must IMMEDIATELY output an empty string without calling any tools.""",
    tools=[read_study_notes, list_available_notes]
)

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
extract_llm = LlmAgent(
    name="extract_llm",
    model="gemini-flash-latest",
    instruction="Analyze the provided study notes. Extract the main topics and subtopics as a structured list.",
    output_schema=TopicStructure
)

@node(name="save_topics_to_state")
def save_topics_to_state(ctx: Context, node_input: TopicStructure):
    current_topics = set(ctx.state.get("extracted_topics", []))
    current_topics.update(node_input.topics)
    
    return Event(
        output={"topics": list(current_topics)},
        state={"extracted_topics": list(current_topics)}
    )

# 3. Quiz Generator
quiz_llm = LlmAgent(
    name="quiz_llm",
    model="gemini-flash-latest",
    instruction="Generate exactly 5 multiple choice questions covering the target topics provided. Include A,B,C,D options.",
    output_schema=QuizQuestions
)

from typing import Any

@node(name="prepare_quiz")
def prepare_quiz(ctx: Context, node_input: Any):
    topics = ctx.state.get("extracted_topics", [])
    scores = ctx.state.get("topic_scores", {})
    
    target_topics = []
    for t in topics:
        if t not in scores or scores[t] < 3:
            target_topics.append(t)
            
    if not target_topics:
        target_topics = topics[:3] if topics else ["General"]
        
    context = retrieve_context(" ".join(target_topics), n_results=5)
    prompt = f"Target Topics: {target_topics}\nContext:\n{context}"
    prompt = resolver.resolve(prompt)
    return Event(output=prompt, state={"current_quiz_topics": target_topics})


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
evaluator_llm = LlmAgent(
    name="evaluator_llm",
    model="gemini-flash-latest",
    instruction="""You are an expert LLM-as-judge. Compare the user's answers to the quiz questions using the provided context.
Score the performance strictly on a 1 to 5 scale (1=Poor, 5=Excellent). Provide detailed feedback.""",
    output_schema=EvaluationResult
)

@node(name="prepare_eval")
def prepare_eval(ctx: Context, node_input: Any):
    quiz = node_input["quiz"]
    answers = node_input["answers"]
    target_topics = ctx.state.get("current_quiz_topics", ["General"])
    context = retrieve_context(" ".join(target_topics), n_results=5)
    
    prompt = f"Context:\n{context}\n\nQuiz Questions:\n{quiz}\n\nUser Answers:\n{answers}"
    prompt = resolver.resolve(prompt)
    return Event(output=prompt)

@node(name="save_eval_to_state")
async def save_eval_to_state(ctx: Context, node_input: EvaluationResult):
    target_topics = ctx.state.get("current_quiz_topics", ["General"])
    
    scores = dict(ctx.state.get("topic_scores", {}))
    for t in target_topics:
        scores[t] = (scores.get(t, node_input.score) + node_input.score) / 2
        
    weak_areas = [t for t, s in scores.items() if s < 3]
    
    # Save progress via direct call
    try:
        save_progress(scores, weak_areas)
    except Exception:
        pass
    
    return Event(
        output={"score": node_input.score, "feedback": node_input.feedback},
        state={"topic_scores": scores, "weak_areas": weak_areas}
    )

# 5. Revision Planner
planner_llm = LlmAgent(
    name="planner_llm",
    model="gemini-flash-latest",
    instruction="Generate a personalized 3-day revision plan allocating time to the provided weak areas.",
    output_schema=RevisionPlan
)

@node(name="prepare_planner")
def prepare_planner(ctx: Context, node_input: Any):
    weak_areas = ctx.state.get("weak_areas", [])
    prompt = f"Weak Areas: {weak_areas}\nRecent Feedback: {node_input['feedback']}"
    prompt = resolver.resolve(prompt)
    return Event(output=prompt)

@node(name="format_final_output")
def format_final_output(ctx: Context, node_input: RevisionPlan):
    weak = ctx.state.get("weak_areas", [])
    scores = ctx.state.get("topic_scores", {})
    return Event(output=f"### Your 3-Day Revision Plan\n{node_input.plan_details}\n\n**Current Weak Areas**: {weak}\n**Topic Scores**: {scores}")


# --- Graph Edges ---
edges = [
    # 0. Load state
    ('START', load_progress_state),
    
    # 1. Ingest via MCP tools
    (load_progress_state, ingest_llm),
    (ingest_llm, chunk_and_embed),
    
    # 2. Extract topics
    (chunk_and_embed, extract_llm),
    (extract_llm, save_topics_to_state),
    
    # 3. Quiz 
    (save_topics_to_state, prepare_quiz),
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
    (planner_llm, format_final_output)
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
