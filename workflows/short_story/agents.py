"""短故事生成管线的三个核心 Agent。"""
from __future__ import annotations
import json
from pathlib import Path
from utils.llm_client import gemini_client

_PROMPT_DIR = Path(__file__).resolve().parent.parent.parent / "prompt_presets" / "short_story"


def _load(name: str, field: str, **kwargs) -> str:
    data = json.loads((_PROMPT_DIR / f"{name}.json").read_text(encoding="utf-8"))
    val = data[field]
    return val.format(**kwargs) if isinstance(val, str) else val


class OutlineConceptAgent:
    def __init__(self, track: str, target_words: int, inspiration: str):
        self.track = track
        self.target_words = target_words
        self.inspiration = inspiration

    def run(self) -> dict:
        system = _load("outline_concept_prompt", "system_prompt")
        user = _load("outline_concept_prompt", "user_prompt",
                     track=self.track, target_words=self.target_words,
                     inspiration=self.inspiration)
        schema = _load("outline_concept_prompt", "json_schema")
        return gemini_client(system, user, schema)


class ContentGenerationAgent:
    def __init__(self, track: str, chapter_outline: str, previous_chapter_ending: str = ""):
        self.track = track
        self.chapter_outline = chapter_outline
        self.previous_chapter_ending = previous_chapter_ending or "（本章为第一章，无前章结尾）"

    def run(self) -> dict:
        system = _load("content_generation_prompt", "system_prompt")
        user = _load("content_generation_prompt", "user_prompt",
                     track=self.track, chapter_outline=self.chapter_outline,
                     previous_chapter_ending=self.previous_chapter_ending)
        schema = _load("content_generation_prompt", "json_schema")
        return gemini_client(system, user, schema)


class ReviewAlignmentAgent:
    def __init__(self, track: str, chapter_text: str):
        self.track = track
        self.chapter_text = chapter_text

    def run(self) -> dict:
        system = _load("review_alignment_prompt", "system_prompt")
        user = _load("review_alignment_prompt", "user_prompt",
                     track=self.track, chapter_text=self.chapter_text)
        schema = _load("review_alignment_prompt", "json_schema")
        return gemini_client(system, user, schema)
