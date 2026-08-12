"""Prompt templates loader utility."""
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent

def load_prompt(filename: str) -> str:
    """Load prompt template text from file."""
    prompt_path = PROMPTS_DIR / filename
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt template file not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")
