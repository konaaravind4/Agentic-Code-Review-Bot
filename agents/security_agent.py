"""
Security analysis agent — detects OWASP vulnerabilities, injection patterns, and secret leaks in code diffs.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import google.generativeai as genai

logger = logging.getLogger(__name__)

INJECTION_PATTERNS = [
    (r"f\".*SELECT.*{.*}.*\"", "SQL injection via f-string"),
    (r"exec\s*\(", "Dynamic exec() call"),
    (r"eval\s*\(", "Dangerous eval() call"),
    (r"subprocess.*shell=True", "Shell injection via subprocess"),
    (r"os\.system\s*\(", "OS command injection"),
    (r'(?i)(password|secret|api_key|token)\s*=\s*["\'][^"\']+["\']', "Hardcoded secret"),
    (r"pickle\.loads?\s*\(", "Insecure pickle deserialization"),
    (r"yaml\.load\s*\([^,)]+\)", "Unsafe YAML load without Loader"),
]


@dataclass
class SecurityIssue:
    line: int
    severity: str  # critical | high | medium | low
    category: str
    description: str
    suggestion: str
    code_snippet: str = ""


@dataclass
class SecurityReport:
    issues: list[SecurityIssue] = field(default_factory=list)
    critical_count: int = 0
    high_count: int = 0
    passed: bool = True


class SecurityAgent:
    """
    Multi-pass security analyzer:
    1. Regex scan for known injection/secret patterns
    2. Gemini LLM deep analysis for complex vulnerability patterns
    """

    SYSTEM_PROMPT = """You are a senior security engineer performing a code review.
Analyze the provided code diff for security vulnerabilities.
Look for: SQL/command injection, hardcoded secrets, insecure deserialization, SSRF, 
path traversal, missing auth, CSRF, XSS, insecure direct object references.

Return a JSON array of issues. Each issue must have:
{
  "line": <int>,
  "severity": "critical" | "high" | "medium" | "low",
  "category": "<string>",
  "description": "<string>",
  "suggestion": "<string fix>"
}

If no issues found, return an empty array [].
Return ONLY valid JSON."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash-lite"):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model, system_instruction=self.SYSTEM_PROMPT)

    def analyze(self, diff: str, filename: str = "") -> SecurityReport:
        """Run full security analysis on a code diff."""
        report = SecurityReport()

        # ── Pass 1: Regex pattern scan ──────────────────────────────
        for i, line in enumerate(diff.splitlines(), 1):
            if not line.startswith("+"):
                continue
            for pattern, label in INJECTION_PATTERNS:
                if re.search(pattern, line):
                    severity = "critical" if "injection" in label.lower() or "secret" in label.lower() else "high"
                    report.issues.append(SecurityIssue(
                        line=i,
                        severity=severity,
                        category="Pattern Match",
                        description=label,
                        suggestion="Review and remediate this pattern immediately.",
                        code_snippet=line.strip()[:120],
                    ))

        # ── Pass 2: LLM deep analysis ─────────────────────────────
        try:
            prompt = f"File: {filename}\n\nCode diff:\n{diff[:8000]}"
            response = self.model.generate_content(prompt)
            raw = response.text.strip()
            raw = re.sub(r"^```json\n?|^```\n?|\n?```$", "", raw, flags=re.MULTILINE)
            llm_issues = json.loads(raw)

            for issue in llm_issues:
                report.issues.append(SecurityIssue(
                    line=issue.get("line", 0),
                    severity=issue.get("severity", "medium"),
                    category=issue.get("category", "LLM Analysis"),
                    description=issue.get("description", ""),
                    suggestion=issue.get("suggestion", ""),
                ))
        except Exception as e:
            logger.warning("LLM security analysis failed: %s", e)

        # Compute summary
        report.critical_count = sum(1 for i in report.issues if i.severity == "critical")
        report.high_count = sum(1 for i in report.issues if i.severity == "high")
        report.passed = report.critical_count == 0

        return report
