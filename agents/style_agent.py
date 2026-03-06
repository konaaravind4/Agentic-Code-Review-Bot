"""
Style enforcement agent — checks PEP8/ESLint alignment and docstring quality.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

import google.generativeai as genai

logger = logging.getLogger(__name__)

PEP8_PATTERNS = [
    (r"def \w+\([^)]*\)\s*:\s*\n(?!\s*(\"\"\"|\'{3}|#))", "Missing docstring"),
    (r"[^\n]{120,}", "Line exceeds 119 characters"),
    (r"\bprint\s*\(", "print() in production code (use logging)"),
    (r"except\s*:", "Bare except clause — catch specific exceptions"),
    (r"import \*", "Wildcard import — specify explicit names"),
]


@dataclass
class StyleIssue:
    line: int
    rule: str
    description: str
    suggestion: str
    severity: str = "low"


@dataclass
class StyleReport:
    issues: list[StyleIssue] = field(default_factory=list)
    pep8_violations: int = 0


class StyleAgent:
    """Checks code style: PEP8, naming conventions, docstrings."""

    SYSTEM_PROMPT = """You are a code style reviewer. Check this diff for style violations:
PEP8 (Python): naming conventions, docstrings, line length, magic numbers, type hints.
ESLint (JS/TS): camelCase, console.log, any types, missing semicolons.
Return JSON: [{"line": int, "rule": str, "description": str, "suggestion": str, "severity": "low"|"medium"}]
Return ONLY valid JSON. Empty [] if none."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash-lite"):
        genai.configure(api_key=api_key)
        self.llm = genai.GenerativeModel(model, system_instruction=self.SYSTEM_PROMPT)

    def analyze(self, diff: str, filename: str = "") -> StyleReport:
        report = StyleReport()

        # Regex pass
        for i, line in enumerate(diff.splitlines(), 1):
            if not line.startswith("+"):
                continue
            for pattern, label in PEP8_PATTERNS:
                if re.search(pattern, line):
                    report.issues.append(StyleIssue(
                        line=i, rule="PEP8", description=label,
                        suggestion="Fix according to PEP8 guidelines.",
                    ))

        # LLM pass
        try:
            response = self.llm.generate_content(f"File: {filename}\n\n{diff[:5000]}")
            raw = re.sub(r"^```json\n?|^```\n?|\n?```$", "", response.text.strip(), flags=re.MULTILINE)
            llm_issues = json.loads(raw)
            for issue in llm_issues:
                report.issues.append(StyleIssue(
                    line=issue.get("line", 0),
                    rule=issue.get("rule", "Style"),
                    description=issue.get("description", ""),
                    suggestion=issue.get("suggestion", ""),
                    severity=issue.get("severity", "low"),
                ))
        except Exception as e:
            logger.warning("Style LLM analysis failed: %s", e)

        report.pep8_violations = len(report.issues)
        return report
