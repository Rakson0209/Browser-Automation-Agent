"""Preset demo tasks (data-model.md PresetTask; FR-007).

Targets stable, publicly accessible, no-login pages so demonstrations are
reproducible (research.md §4/§6) — the Hacker News front page is kept available
per the source PDF even though it proved less reliable in some environments,
since the project's own history documents it working fine in the deployed
(cloud) environment.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class PresetTask:
    key: str
    label: str
    goal: str
    start_url: str


PRESETS: List[PresetTask] = [
    PresetTask(
        key="quotes_humor",
        label="Collect humor quotes",
        goal=(
            "Collect all humor-tagged quotes from quotes.toscrape.com, including "
            "any that appear on later pages."
        ),
        start_url="https://quotes.toscrape.com/tag/humor/",
    ),
    PresetTask(
        key="hacker_news_top",
        label="Summarize Hacker News front page",
        goal="Read the titles of the top stories on the Hacker News front page and summarize them.",
        start_url="https://news.ycombinator.com/",
    ),
]


def get_preset(key: str) -> Optional[PresetTask]:
    for preset in PRESETS:
        if preset.key == key:
            return preset
    return None
