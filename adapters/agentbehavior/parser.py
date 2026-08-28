"""AgentBehavior BEHAVIOR.md parser.

Parses AgentBehavior specification markdown files into structured dictionaries
containing Intent, Evidence, Decision, Execution, Recovery, and Failure Modes.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional


def _normalize_section_title(title: str) -> str:
    """Normalize a markdown section title to a standard snake_case key."""
    # Remove leading numbering like '1.', '1. ', 'Section 1:'
    cleaned = re.sub(r"^(?:section\s+)?\d+[\.\:\-\s]*", "", title.strip(), flags=re.IGNORECASE)
    # Convert spaces/hyphens to underscore and lowercase
    cleaned = re.sub(r"[\s\-]+", "_", cleaned.strip().lower())
    return cleaned


def _parse_decision_bullets(text: str) -> Dict[str, str]:
    """Parse Decision section bullets into true/false/na mapping."""
    decisions: Dict[str, str] = {
        "true": "",
        "false": "",
        "na": "",
        "raw": text.strip(),
    }

    # Match patterns like `- `true`: explanation` or `- true: explanation` or `* `true`: ...`
    pattern = re.compile(
        r"^[\*\-]\s*[`'\"]?(true|false|na)[`'\"]?\s*:\s*(.+)$",
        re.IGNORECASE | re.MULTILINE,
    )

    for match in pattern.finditer(text):
        verdict = match.group(1).lower()
        explanation = match.group(2).strip()
        decisions[verdict] = explanation

    return decisions


def parse_behavior_md(content: str) -> Dict[str, Any]:
    """Parse an AgentBehavior BEHAVIOR.md markdown document into a structured dict.

    Args:
        content: The raw markdown string content of a BEHAVIOR.md file.

    Returns:
        Dict[str, Any] containing:
            - name: The behavior name extracted from title.
            - intent: The intent section text.
            - evidence: The evidence section text.
            - decision: Dict containing true, false, na, and raw decision criteria.
            - execution: The execution section text.
            - recovery: The recovery section text.
            - failure_modes: The failure modes section text.
            - sections: Dictionary mapping all raw/custom section names to their text.
            - raw: The full original markdown content.
    """
    if not content or not content.strip():
        return {
            "name": "",
            "intent": "",
            "evidence": "",
            "decision": {"true": "", "false": "", "na": "", "raw": ""},
            "execution": "",
            "recovery": "",
            "failure_modes": "",
            "sections": {},
            "raw": content,
        }

    lines = content.splitlines()
    behavior_name = ""
    sections: Dict[str, str] = {}
    current_section: Optional[str] = None
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Check for top-level title: # BEHAVIOR: <name> or # <name>
        h1_match = re.match(r"^#\s+(?:BEHAVIOR\s*:\s*)?(.+)$", stripped, re.IGNORECASE)
        if h1_match and not behavior_name:
            behavior_name = h1_match.group(1).strip()
            continue

        # Check for section header (## or ###)
        h2_match = re.match(r"^#{2,3}\s+(.+)$", stripped)
        if h2_match:
            if current_section is not None:
                sections[current_section] = "\n".join(current_lines).strip()
                current_lines = []
            raw_title = h2_match.group(1).strip()
            current_section = _normalize_section_title(raw_title)
            continue

        if current_section is not None:
            current_lines.append(line)

    if current_section is not None:
        sections[current_section] = "\n".join(current_lines).strip()

    # Extract standard fields with fallbacks
    intent = sections.get("intent", "")
    evidence = sections.get("evidence", "")
    raw_decision = sections.get("decision", "")
    decision_dict = _parse_decision_bullets(raw_decision)
    execution = sections.get("execution", "")
    recovery = sections.get("recovery", "")
    failure_modes = (
        sections.get("failure_modes")
        or sections.get("failure_mode")
        or sections.get("failures")
        or ""
    )

    return {
        "name": behavior_name,
        "intent": intent,
        "evidence": evidence,
        "decision": decision_dict,
        "execution": execution,
        "recovery": recovery,
        "failure_modes": failure_modes,
        "sections": sections,
        "raw": content,
    }


def load_behavior_file(path: str | Path) -> Dict[str, Any]:
    """Load and parse an AgentBehavior BEHAVIOR.md file from disk.

    Args:
        path: Path to the BEHAVIOR.md file.

    Returns:
        Dict[str, Any] parsed behavior dictionary.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Behavior file not found: {file_path}")

    content = file_path.read_text(encoding="utf-8")
    parsed = parse_behavior_md(content)

    # If behavior name wasn't in H1 title, fallback to parent directory name
    if not parsed["name"]:
        parsed["name"] = file_path.parent.name

    return parsed
