"""The rule record: one provision of the Handbook, and how records are stored."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .ids import cite


@dataclass
class Rule:
    """One Handbook provision, as parsed from a sourcebook PDF."""

    id: str                  # "DISP 1.6.2"
    type: str                # "R", "G", "E", "D", ... ("" for annexes and schedules)
    book: str                # "DISP"
    kind: str                # "rule", "annex", "app", "sch", "tp", "intro"
    chapter: str             # "DISP 1"
    section: str             # "DISP 1.6"
    section_title: str = ""  # "Complaints time limit rules"
    heading: str = ""        # the nearest subheading above it, if any
    text: str = ""           # the provision's text, list items on their own lines
    page: int = 0            # first page in the PDF, counting from 1
    refs: list[str] = field(default_factory=list)   # provisions it refers to
    terms: list[str] = field(default_factory=list)  # Glossary terms it uses (italic in the PDF)
    deleted: bool = False    # the provision is marked [deleted]

    @property
    def citation(self) -> str:
        return cite(self.id, self.type)


def save_rules(rules: list[Rule], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rules:
            f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")


def load_rules(path: Path, include_deleted: bool = False) -> list[Rule]:
    rules = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            r = Rule(**json.loads(line))
            if include_deleted or not r.deleted:
                rules.append(r)
    return rules
