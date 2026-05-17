"""
Coordinator agent — runs Security, Performance, and Style agents in parallel.
"""
from __future__ import annotations

import concurrent.futures
import logging
import os
from dataclasses import dataclass, field

from agents.security_agent import SecurityAgent, SecurityReport
from agents.performance_agent import PerformanceAgent, PerfReport
from agents.style_agent import StyleAgent, StyleReport

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


@dataclass
class CodeReviewResult:
    security: SecurityReport
    performance: PerfReport
    style: StyleReport
    summary: str = ""
    total_issues: int = 0
    passed: bool = True

    def __post_init__(self) -> None:
        all_issues = (
            len(self.security.issues)
            + len(self.performance.issues)
            + len(self.style.issues)
        )
        self.total_issues = all_issues
        self.passed = self.security.passed  # fail only on critical security issues

    def format_github_comment(self) -> str:
        """Generate a formatted GitHub PR comment."""
        lines = [
            "## 🤖 Agentic Code Review",
            "",
            f"{'✅ Passed' if self.passed else '❌ Failed'} | "
            f"{len(self.security.issues)} security | "
            f"{len(self.performance.issues)} performance | "
            f"{len(self.style.issues)} style",
            "",
        ]

        if self.security.issues:
            lines.append("### 🔒 Security Issues")
            for issue in self.security.issues:
                emoji = "🚨" if issue.severity == "critical" else "⚠️"
                lines.append(f"- {emoji} **Line {issue.line}** [{issue.severity.upper()}] {issue.description}")
                lines.append(f"  > 💡 {issue.suggestion}")
            lines.append("")

        if self.performance.issues:
            lines.append("### ⚡ Performance Issues")
            for issue in self.performance.issues:
                lines.append(f"- ⚡ **Line {issue.line}** {issue.description}")
                lines.append(f"  > 💡 {issue.suggestion}")
            lines.append("")

        if self.style.issues:
            lines.append("### 🎨 Style Issues")
            for issue in self.style.issues[:10]:  # cap at 10 for readability
                lines.append(f"- 🎨 **Line {issue.line}** `{issue.rule}` {issue.description}")
            lines.append("")

        if not (self.security.issues or self.performance.issues or self.style.issues):
            lines.append("✨ **No issues found! Clean code.**")

        return "\n".join(lines)


class CodeReviewCoordinator:
    """
    Orchestrates the 3 specialist agents in parallel using ThreadPoolExecutor.
    Mirrors Google ADK's ParallelAgent pattern.
    """

    def __init__(self, api_key: str = GEMINI_API_KEY, max_workers: int = 3):
        self.security_agent = SecurityAgent(api_key=api_key)
        self.perf_agent = PerformanceAgent(api_key=api_key)
        self.style_agent = StyleAgent(api_key=api_key)
        self.max_workers = max_workers

    def review(self, diff: str, filename: str = "") -> CodeReviewResult:
        """
        Run all 3 agents in parallel, merge results into a CodeReviewResult.
        Target: < 45s end-to-end.
        """
        logger.info("Starting parallel code review for %s (%d chars)", filename, len(diff))

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            sec_future = executor.submit(self.security_agent.analyze, diff, filename)
            perf_future = executor.submit(self.perf_agent.analyze, diff, filename)
            style_future = executor.submit(self.style_agent.analyze, diff, filename)

            security = sec_future.result(timeout=40)
            performance = perf_future.result(timeout=40)
            style = style_future.result(timeout=40)

        result = CodeReviewResult(security=security, performance=performance, style=style)
        logger.info(
            "Review complete: %d total issues (%s)",
            result.total_issues,
            "PASS" if result.passed else "FAIL",
        )
        return result
