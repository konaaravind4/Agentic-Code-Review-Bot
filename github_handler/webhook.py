"""
GitHub PR webhook handler — receives and validates GitHub webhook payloads.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")


def verify_signature(payload: bytes, signature: str) -> bool:
    """Verify GitHub HMAC-SHA256 webhook signature."""
    if not WEBHOOK_SECRET:
        logger.warning("GITHUB_WEBHOOK_SECRET not set — skipping signature verification")
        return True
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


async def parse_pr_event(request: Request) -> dict | None:
    """
    Parse incoming GitHub PR webhook event.
    Returns PR metadata or None if not a reviewable event.
    """
    signature = request.headers.get("X-Hub-Signature-256", "")
    event_type = request.headers.get("X-GitHub-Event", "")

    body = await request.body()

    if not verify_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    if event_type not in ("pull_request",):
        return None

    payload = json.loads(body)
    action = payload.get("action", "")

    if action not in ("opened", "synchronize", "reopened"):
        return None

    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})

    return {
        "pr_number": pr.get("number"),
        "pr_title": pr.get("title"),
        "base_sha": pr.get("base", {}).get("sha"),
        "head_sha": pr.get("head", {}).get("sha"),
        "repo_owner": repo.get("owner", {}).get("login"),
        "repo_name": repo.get("name"),
        "diff_url": pr.get("diff_url"),
        "action": action,
    }
