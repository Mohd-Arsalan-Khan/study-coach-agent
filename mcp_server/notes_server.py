import os
import json
from mcp.server.fastmcp import FastMCP
import sys
import docx

# Ensure app module is importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.security.permissions import SecurityEnforcer

# Initialize FastMCP server
mcp = FastMCP("NotesServer")

# Use absolute paths relative to the project root
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
NOTES_DIR = os.path.join(BASE_DIR, "notes")
PROGRESS_FILE = os.path.join(BASE_DIR, "progress.json")

# Initialize SecurityEnforcer
enforcer = SecurityEnforcer(NOTES_DIR, PROGRESS_FILE)

@mcp.tool()
def read_study_notes(filepath: str) -> str:
    """Reads the text content of a docx or txt file."""
    try:
        valid_path = enforcer.validate_read(filepath)
    except PermissionError as pe:
        return str(pe)
        
    if not os.path.exists(valid_path):
        return f"Error: File '{valid_path}' does not exist."
    
    if valid_path.endswith(".docx"):
        try:
            doc = docx.Document(valid_path)
            return "\n".join([para.text for para in doc.paragraphs])
        except Exception as e:
            return f"Error reading docx: {e}"
    elif valid_path.endswith(".txt"):
        try:
            with open(valid_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Error reading txt: {e}"
    else:
        return "Error: Unsupported file format. Only .docx and .txt are supported."

@mcp.tool()
def list_available_notes() -> list[str]:
    """Lists all files available in the notes/ directory."""
    if not os.path.exists(NOTES_DIR):
        return []
    return [os.path.join(NOTES_DIR, f) for f in os.listdir(NOTES_DIR) if os.path.isfile(os.path.join(NOTES_DIR, f))]

@mcp.tool()
def save_progress(topic_scores: dict, weak_areas: list) -> str:
    """Saves quiz scores and weak areas to progress.json so they persist between sessions."""
    data = {
        "topic_scores": topic_scores,
        "weak_areas": weak_areas
    }
    try:
        valid_path = enforcer.validate_write(PROGRESS_FILE)
        with open(valid_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        return f"Progress successfully saved to {valid_path}"
    except Exception as e:
        return f"Error saving progress: {e}"

@mcp.tool()
def load_progress() -> dict:
    """Loads previous quiz scores and weak areas from progress.json."""
    try:
        valid_path = enforcer.validate_read(PROGRESS_FILE)
        if not os.path.exists(valid_path):
            return {"topic_scores": {}, "weak_areas": []}
            
        with open(valid_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except PermissionError:
        return {"topic_scores": {}, "weak_areas": []}
    except Exception as e:
        return {"topic_scores": {}, "weak_areas": []}

if __name__ == "__main__":
    # Start the server using stdio transport
    mcp.run(transport='stdio')
