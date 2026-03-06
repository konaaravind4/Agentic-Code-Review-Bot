"""
GitHub PR inline comment poster using PyGithub.
"""
from __future__ import annotations

import logging
import os

from github import Github, GithubException

logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")


class PRCommenter:
    """Posts review comments on GitHub PRs."""

    def __init__(self, token: str = GITHUB_TOKEN):
        self.gh = Github(token)

    def post_review(
        self,
        repo_owner: str,
        repo_name: str,
        pr_number: int,
        body: str,
        approve: bool = False,
    ) -> bool:
        """Post a review comment on a PR."""
        try:
            repo = self.gh.get_repo(f"{repo_owner}/{repo_name}")
            pr = repo.get_pull(pr_number)
            event = "APPROVE" if approve else "COMMENT"
            pr.create_review(body=body, event=event)
            logger.info("Posted review on PR #%d in %s/%s", pr_number, repo_owner, repo_name)
            return True
        except GithubException as e:
            logger.error("Failed to post PR review: %s", e)
            return False

    def post_issue_comment(
        self,
        repo_owner: str,
        repo_name: str,
        pr_number: int,
        body: str,
    ) -> bool:
        """Post a general issue comment (simpler than review)."""
        try:
            repo = self.gh.get_repo(f"{repo_owner}/{repo_name}")
            issue = repo.get_issue(pr_number)
            issue.create_comment(body)
            return True
        except GithubException as e:
            logger.error("Failed to post comment: %s", e)
            return False

    def get_pr_diff(self, repo_owner: str, repo_name: str, pr_number: int) -> str:
        """Fetch the full diff for a PR."""
        import requests
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3.diff",
        }
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls/{pr_number}"
        resp = requests.get(url, headers=headers, timeout=30)
        return resp.text if resp.ok else ""
