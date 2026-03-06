"""
FastAPI webhook endpoint for Agentic Code Review Bot.
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from agents.coordinator import CodeReviewCoordinator
from github_handler.webhook import parse_pr_event
from github_handler.commenter import PRCommenter

logger = logging.getLogger(__name__)

coordinator: CodeReviewCoordinator | None = None
commenter: PRCommenter | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global coordinator, commenter
    coordinator = CodeReviewCoordinator()
    commenter = PRCommenter()
    yield


app = FastAPI(
    title="Agentic Code Review Bot",
    description="Multi-agent GitHub PR reviewer — Security + Performance + Style",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "agents": ["security", "performance", "style"]}


@app.post("/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks) -> dict:
    """Receive GitHub PR webhook and trigger async review."""
    pr_data = await parse_pr_event(request)
    if not pr_data:
        return {"status": "ignored"}

    background_tasks.add_task(run_review, pr_data)
    return {"status": "review_queued", "pr": pr_data["pr_number"]}


async def run_review(pr_data: dict) -> None:
    """Run the full code review pipeline asynchronously."""
    t0 = time.monotonic()
    try:
        diff = commenter.get_pr_diff(
            pr_data["repo_owner"], pr_data["repo_name"], pr_data["pr_number"]
        )
        if not diff:
            logger.warning("Empty diff for PR #%d", pr_data["pr_number"])
            return

        result = coordinator.review(diff, filename=pr_data.get("pr_title", ""))
        comment = result.format_github_comment()

        commenter.post_issue_comment(
            pr_data["repo_owner"],
            pr_data["repo_name"],
            pr_data["pr_number"],
            comment,
        )

        elapsed = time.monotonic() - t0
        logger.info(
            "Review for PR #%d complete in %.1fs — %d issues",
            pr_data["pr_number"], elapsed, result.total_issues
        )
    except Exception as e:
        logger.error("Review failed for PR #%d: %s", pr_data.get("pr_number"), e)


@app.post("/review/direct")
async def direct_review(request: Request) -> dict:
    """Direct review endpoint for testing — accepts {'diff': '...', 'filename': '...'}."""
    body = await request.json()
    diff = body.get("diff", "")
    filename = body.get("filename", "")
    if not diff:
        return {"error": "diff is required"}
    result = coordinator.review(diff, filename=filename)
    return {
        "passed": result.passed,
        "total_issues": result.total_issues,
        "security_issues": len(result.security.issues),
        "performance_issues": len(result.performance.issues),
        "style_issues": len(result.style.issues),
        "comment": result.format_github_comment(),
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8004, reload=False)
