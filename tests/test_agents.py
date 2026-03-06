"""
Tests for Agentic Code Review Bot agents.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

VULNERABLE_DIFF = """+    query = f"SELECT * FROM users WHERE id = {user_id}"
+    password = 'hardcoded_secret_123'
+    result = eval(user_input)
"""

CLEAN_DIFF = """+    query = "SELECT * FROM users WHERE id = %s"
+    result = db.execute(query, (user_id,))
+    return result.fetchall()
"""


class TestSecurityAgent:
    @patch("agents.security_agent.genai")
    def test_detects_sql_injection(self, mock_genai):
        from agents.security_agent import SecurityAgent

        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model
        mock_model.generate_content.return_value.text = "[]"

        agent = SecurityAgent(api_key="test")
        report = agent.analyze(VULNERABLE_DIFF, "views.py")

        # Regex should catch the f-string SQL injection
        assert any("injection" in issue.description.lower() or "SQL" in issue.description
                   for issue in report.issues)

    @patch("agents.security_agent.genai")
    def test_clean_code_has_no_regex_issues(self, mock_genai):
        from agents.security_agent import SecurityAgent

        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model
        mock_model.generate_content.return_value.text = "[]"

        agent = SecurityAgent(api_key="test")
        report = agent.analyze(CLEAN_DIFF, "views.py")
        # Regex should not flag parameterized queries
        regex_issues = [i for i in report.issues if i.category == "Pattern Match"]
        assert len(regex_issues) == 0

    @patch("agents.security_agent.genai")
    def test_hardcoded_secret_detected(self, mock_genai):
        from agents.security_agent import SecurityAgent

        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model
        mock_model.generate_content.return_value.text = "[]"

        agent = SecurityAgent(api_key="test")
        report = agent.analyze(VULNERABLE_DIFF, "config.py")
        assert any("secret" in issue.description.lower() or "hardcoded" in issue.description.lower()
                   for issue in report.issues)


class TestStyleAgent:
    @patch("agents.style_agent.genai")
    def test_detects_bare_except(self, mock_genai):
        from agents.style_agent import StyleAgent

        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model
        mock_model.generate_content.return_value.text = "[]"

        agent = StyleAgent(api_key="test")
        diff = "+    except:\n+        pass\n"
        report = agent.analyze(diff, "app.py")
        assert any("bare except" in issue.description.lower() or "Bare" in issue.description
                   for issue in report.issues)


class TestCoordinator:
    @patch("agents.coordinator.StyleAgent")
    @patch("agents.coordinator.PerformanceAgent")
    @patch("agents.coordinator.SecurityAgent")
    def test_review_returns_result(self, mock_sec_cls, mock_perf_cls, mock_style_cls):
        from agents.coordinator import CodeReviewCoordinator
        from agents.security_agent import SecurityReport
        from agents.performance_agent import PerfReport
        from agents.style_agent import StyleReport

        mock_sec_cls.return_value.analyze.return_value = SecurityReport()
        mock_perf_cls.return_value.analyze.return_value = PerfReport()
        mock_style_cls.return_value.analyze.return_value = StyleReport()

        coord = CodeReviewCoordinator(api_key="test")
        result = coord.review(CLEAN_DIFF, "test.py")

        assert result.total_issues == 0
        assert result.passed is True

    @patch("agents.coordinator.StyleAgent")
    @patch("agents.coordinator.PerformanceAgent")
    @patch("agents.coordinator.SecurityAgent")
    def test_format_github_comment_no_issues(self, mock_sec_cls, mock_perf_cls, mock_style_cls):
        from agents.coordinator import CodeReviewCoordinator
        from agents.security_agent import SecurityReport
        from agents.performance_agent import PerfReport
        from agents.style_agent import StyleReport

        mock_sec_cls.return_value.analyze.return_value = SecurityReport()
        mock_perf_cls.return_value.analyze.return_value = PerfReport()
        mock_style_cls.return_value.analyze.return_value = StyleReport()

        coord = CodeReviewCoordinator(api_key="test")
        result = coord.review(CLEAN_DIFF)
        comment = result.format_github_comment()
        assert "Agentic Code Review" in comment
        assert "Clean code" in comment or "No issues" in comment
