"""Versioned system prompts. The file name (without .md) is the prompt version."""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent
DEFAULT_VERSION = "v1"


def load_system_prompt(version: str = DEFAULT_VERSION) -> str:
    path = PROMPTS_DIR / f"{version}.md"
    if not path.is_file():
        raise ValueError(f"Unknown prompt version: {version}")
    return path.read_text(encoding="utf-8").strip()


def available_versions() -> list[str]:
    return sorted(p.stem for p in PROMPTS_DIR.glob("*.md"))
