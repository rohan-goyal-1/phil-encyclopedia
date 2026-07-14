from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Level = Literal["elementary", "middle", "high_school"]


class ImportantTerm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term: str = Field(min_length=1, max_length=80)
    definition: str = Field(min_length=1, max_length=280)


class LevelSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=80, max_length=1800)
    key_ideas: list[str] = Field(min_length=2, max_length=6)
    important_terms: list[ImportantTerm] = Field(min_length=2, max_length=8)
    example: str = Field(min_length=40, max_length=700)
    why_it_matters: str = Field(min_length=40, max_length=700)
    questions_to_think_about: list[str] = Field(min_length=2, max_length=5)
    reading_time_minutes: int = Field(ge=1, le=10)


class GeneratedArticle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sep_slug: str
    sep_url: str = Field(pattern=r"^https://plato\.stanford\.edu/entries/.+/$")
    title: str = Field(min_length=1, max_length=300)
    source_title: str = Field(min_length=1, max_length=300)
    attribution: str = Field(pattern=r"^Based on the Stanford Encyclopedia of Philosophy entry:")
    read_more_url: str = Field(pattern=r"^https://plato\.stanford\.edu/entries/.+/$")
    elementary: LevelSummary
    middle: LevelSummary
    high_school: LevelSummary
    sensitive_topic: bool
    sensitive_topic_reasons: list[str] = Field(max_length=10)


class BatchResultEnvelope(BaseModel):
    custom_id: str
    response: dict | None = None
    error: dict | None = None


def json_schema() -> dict:
    return openai_strict_schema(GeneratedArticle.model_json_schema())


def openai_strict_schema(schema: dict) -> dict:
    cleaned = dict(schema)
    _clean_schema_node(cleaned)
    return cleaned


def _clean_schema_node(node: object) -> None:
    if isinstance(node, dict):
        node.pop("default", None)
        node.pop("format", None)
        if node.get("type") == "object":
            properties = node.get("properties", {})
            node["additionalProperties"] = False
            node["required"] = list(properties.keys())
        for value in node.values():
            _clean_schema_node(value)
    elif isinstance(node, list):
        for value in node:
            _clean_schema_node(value)
