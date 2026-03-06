"""
Performance analysis agent — detects O(n²), N+1 queries, memory leaks, blocking I/O.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import google.generativeai as genai

logger = logging.getLogger(__name__)

COMPLEXITY_PATTERNS = [
    (r"for\s+\w+\s+in.*:\s*\n\s+for\s+\w+\s+in", "Nested loop (O(n²) risk)"),
    (r"\.filter\(.*\).*\.all\(\)", "Possible N+1 ORM query — use select_related/prefetch_related"),
    (r"for\s+\w+\s+in.*:\s*\n\s+.*\.query\(", "Probable N+1 database query in loop"),
    (r"time\.sleep\s*\(", "Blocking sleep in synchronous code"),
    (r"requests\.get\s*\(", "Synchronous HTTP in possibly async context"),
    (r"\+\s*=\s*\[.*\]", "List concatenation in loop (use .append or extend)"),
    (r"(?i)SELECT \*", "SELECT * — specify columns to avoid over-fetching"),
]


@dataclass
class PerfIssue:
    line: int
    severity: str
    pattern: str
    description: str
    suggestion: str


@dataclass
class PerfReport:
    issues: list[PerfIssue] = field(default_factory=list)
    complexity_warnings: int = 0


class PerformanceAgent:
    """Detects performance anti-patterns via regex + Gemini deep analysis."""

    SYSTEM_PROMPT = """You are a senior performance engineer reviewing a code diff.
Identify performance anti-patterns: O(n²) algorithms, N+1 queries, unnecessary re-renders,
memory leaks, blocking I/O, inefficient data structures, missing indexes.

Return a JSON array of issues:
[{"line": int, "severity": "high"|"medium"|"low", "pattern": str, "description": str, "suggestion": str}]

Return ONLY valid JSON. Empty array [] if no issues."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash-lite"):
        genai.configure(api_key=api_key)
        self.llm = genai.GenerativeModel(model, system_instruction=self.SYSTEM_PROMPT)

    def analyze(self, diff: str, filename: str = "") -> PerfReport:
        report = PerfReport()

        # Regex pass
        for i, line in enumerate(diff.splitlines(), 1):
            if not line.startswith("+"):
                continue
            for pattern, label in COMPLEXITY_PATTERNS:
                if re.search(pattern, line, re.MULTILINE):
                    report.issues.append(PerfIssue(
                        line=i,
                        severity="medium",
                        pattern=label,
                        description=f"Detected: {label}",
                        suggestion="Review this pattern for performance implications.",
                    ))

        # LLM pass
        try:
            response = self.llm.generate_content(f"File: {filename}\n\n{diff[:6000]}")
            raw = re.sub(r"^```json\n?|^```\n?|\n?```$", "", response.text.strip(), flags=re.MULTILINE)
            llm_issues = json.loads(raw)
            for issue in llm_issues:
                report.issues.append(PerfIssue(
                    line=issue.get("line", 0),
                    severity=issue.get("severity", "medium"),
                    pattern=issue.get("pattern", ""),
                    description=issue.get("description", ""),
                    suggestion=issue.get("suggestion", ""),
                ))
        except Exception as e:
            logger.warning("LLM performance analysis failed: %s", e)

        report.complexity_warnings = len([i for i in report.issues if "O(n" in i.pattern])
        return report
