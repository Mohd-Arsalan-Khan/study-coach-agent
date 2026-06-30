# 🎓 Study Coach Agent

> An AI-powered personal study coach built with Google ADK 2.0 that quizzes you from your own notes, tracks your weak areas, and creates personalized revision plans — all with enterprise-grade security.

Built for the **Google × Kaggle 5-Day AI Agents: Intensive Vibe Coding Capstone** | Track: Agents for Good

---

## 🎯 The Problem

Students waste hours passively re-reading notes without knowing what to focus on. There is no personalized feedback, no tracking of weak areas, and no intelligent study planning. Traditional flashcard apps are static and generic — they don't adapt to *you*.

## 💡 The Solution

The Study Coach Agent transforms your own study notes into an intelligent, adaptive learning experience:

- 📄 Upload your notes → agent reads and indexes them
- 🧠 Get quizzed on topics you need to practice most
- 📊 Agent tracks your scores and identifies weak areas
- 📅 Generates a personalized 3-day revision plan
- 🔔 Sends ambient daily study reminders automatically

---

## 🏗️ Architecture

```
User uploads notes
        ↓
┌─────────────────────────────────────────┐
│           ADK 2.0 Graph                 │
│                                         │
│  RouterNode → IngestionNode             │
│       ↓                                 │
│  QuizNode (quiz-generator skill)        │
│       ↓                                 │
│  EvaluatorNode (LLM-as-judge)          │
│       ↓                                 │
│  PlannerNode (revision-planner skill)   │
│       ↓                                 │
│  AmbientReminderNode (background)       │
└─────────────────────────────────────────┘
        ↓
MCP Server (notes reader + progress tracker)
        ↓
Security Layer (PII redaction + prompt injection defense)
        ↓
Google Cloud Agent Runtime (production)
```

---

## ✨ Key Features

### 🤖 Intelligent Quiz Generation
- Generates 5 questions per session mixing multiple choice, short answer, and application questions
- Prioritizes topics where you scored below 60% in previous sessions
- Uses RAG pipeline to retrieve only relevant content from your notes

### 📊 LLM-as-Judge Evaluation
- Scores your answers on a 1-5 scale with detailed feedback
- Tracks weak areas across sessions in persistent state
- Uses trajectory scoring to measure improvement over time

### 📅 Personalized Revision Planning
- Reads your quiz history to identify the weakest topics
- Generates a structured 3-day revision schedule
- Includes time allocations, study methods, and key concepts to focus on

### 🔔 Ambient Study Reminders
- Pub/Sub endpoint triggers study sessions from external events
- Daily background task sends personalized reminders
- Progress webhooks update revision plans automatically

### 🛡️ Enterprise Security
- PII redaction before any LLM call
- Prompt injection detection and blocking
- Zero Ambient Authority — agent only accesses what it needs
- Pre-commit Semgrep security gates
- STRIDE threat model assessment
- Context Hygiene to prevent session data leakage

---

## 🗂️ Project Structure

```
study-coach-agent/
├── app/
│   ├── agent.py                    # Main ADK 2.0 graph with 5 nodes
│   ├── server.py                   # FastAPI ambient trigger server
│   └── security/
│       ├── context_resolver.py     # PII masking and context hygiene
│       ├── permissions.py          # Zero ambient authority controls
│       └── sanitizer.py           # Prompt injection defense
├── .agents/
│   ├── skills/
│   │   ├── quiz-generator/
│   │   │   └── SKILL.md           # Quiz generation skill
│   │   ├── revision-planner/
│   │   │   └── SKILL.md           # Revision planning skill
│   │   └── stride-threat-model/
│   │       └── SKILL.md           # Security assessment skill
│   ├── hooks.json                  # PreToolUse agent hooks
│   └── CONTEXT.md                 # Agent context rules
├── mcp_server/
│   └── notes_server.py            # MCP server for notes + progress
├── notes/                         # Drop your study notes here
├── tests/
│   ├── eval/
│   │   ├── datasets/
│   │   │   └── basic-dataset.json # 5 evaluation scenarios
│   │   ├── eval_config.yaml       # LLM-as-judge metrics config
│   │   ├── generate_traces.py     # Trace generation script
│   │   └── grade_traces.py        # Grading script
│   └── test_agent.py              # Unit tests
├── .semgrep/
│   └── rules.yaml                 # Custom security scanning rules
├── .pre-commit-config.yaml        # Pre-commit security hooks
├── .cloudbuild/
│   └── deploy-to-prod.yaml        # Google Cloud Build CI/CD
├── pyproject.toml                 # Dependencies
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- [Google Antigravity IDE](https://antigravity.google)
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey)

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/study-coach-agent.git
cd study-coach-agent

# Install dependencies
uv sync

# Set your API key
export GEMINI_API_KEY="your-api-key-here"   # Mac/Linux
$env:GEMINI_API_KEY = "your-api-key-here"   # Windows PowerShell
```

> **Note on model provider:** This project defaults to NVIDIA NIM (Llama 3.3 70B Instruct via an OpenAI-compatible endpoint) rather than Gemini directly. This is because Gemini's free tier (20 requests/day) is too restrictive for iterative development and evaluation runs, while NVIDIA NIM's free tier (40 requests/minute, no daily cap) supports a much smoother dev loop. ADK 2.0 is model-agnostic, so switching providers required only a configuration change — no changes to the graph, skills, or security layer. To use NVIDIA NIM instead, get a free key at [build.nvidia.com](https://build.nvidia.com) and set `NVIDIA_API_KEY` in your `.env` file. The Gemini code path remains available as a fallback via `GEMINI_API_KEY`.

### Add Your Notes

Drop any `.txt` or `.docx` study notes into the `notes/` directory:

```
notes/
  my_course_notes.txt
  lecture_slides.docx
```

### Run Locally

```bash
# Start the ADK Playground
uv run adk web app --host 127.0.0.1 --port 8080
```

Open your browser at: `http://127.0.0.1:8080/dev-ui/?app=app`

Then chat with your study coach:
```
I have uploaded my notes. Please quiz me on the topic of Machine Learning.
```

### Run the Ambient Server

```bash
uv run python app/server.py
```

Trigger a study session via PowerShell:
```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/trigger/pubsub" `
  -Method Post `
  -Headers @{"Content-Type"="application/json"} `
  -Body '{"student_id": "user123", "action": "start_quiz", "topic": "MCP"}'
```

---

## 🧪 Running Evaluations

```bash
# Generate traces from test scenarios
uv run python tests/eval/generate_traces.py

# Grade traces with LLM-as-judge
uv run python tests/eval/grade_traces.py
```

### Evaluation Metrics

| Metric | What it measures | Target |
|--------|-----------------|--------|
| `quiz_quality` | Do questions test real understanding vs memorization? | 5/5 |
| `revision_relevance` | Does the plan match the user's actual weak areas? | 5/5 |

---

## 🔒 Security Features

### Pre-commit Gates
```bash
# Install hooks
uv run pre-commit install

# Run security scan manually
uv run semgrep --error --config .semgrep/rules.yaml app/
```

### Agent Hooks
The `.agents/hooks.json` intercepts all `run_command` executions before they run, blocking destructive commands like `rm -rf /`.

### STRIDE Threat Model
Run the built-in security assessment:
```
# In Antigravity chat:
Run stride-threat-model on our study-coach-agent project
```

---

## ☁️ Deploy to Google Cloud

### Prerequisites
- Google Cloud project with billing enabled
- `gcloud` CLI installed and authenticated
- Secret Manager secret named `GEMINI_API_KEY`

### Deploy

```bash
uvx google-agents-cli deploy \
  --project YOUR_PROJECT_ID \
  --region us-central1 \
  --secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest"
```

### CI/CD Pipeline

The `.cloudbuild/deploy-to-prod.yaml` pipeline automatically:
- Runs security scans on every PR
- Deploys to staging on merge to `main`
- Promotes to production after manual approval

---

## 🧩 Course Concepts Demonstrated

| Concept | Where |
|---------|-------|
| ADK 2.0 Multi-agent graph | `app/agent.py` |
| MCP Server | `mcp_server/notes_server.py` |
| Agent Skills | `.agents/skills/` |
| Security features | `app/security/` + `.semgrep/` |
| Antigravity vibe coding | Used throughout development |
| Cloud deployability | `.cloudbuild/` + `agents-cli deploy` |
| LLM-as-judge evaluation | `tests/eval/` |
| STRIDE threat modeling | `.agents/skills/stride-threat-model/` |
| Ambient triggers | `app/server.py` |
| Context Hygiene | `app/security/context_resolver.py` |

---

## 🌍 Track

**Agents for Good** — helping students learn more effectively through personalized AI coaching

---

## 👤 Author

**Mohd Arsalan Khan**
Completed Google × Kaggle 5-Day AI Agents: Intensive Vibe Coding Course

🏅 [View Badge](https://developers.google.com/profile/badges/events/cloud/five-day-ai-agents)

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
