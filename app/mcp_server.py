from __future__ import annotations

from typing import Literal, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .database import Base, SessionLocal, engine
from .services.focus_tools import execute_focus_tool


def _call(name: str, arguments: dict | None = None) -> dict:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        result = execute_focus_tool(db, name, arguments)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_focus_mcp(**kwargs) -> FastMCP:
    server = FastMCP(
        "FocusWith",
        instructions=(
            "Use these tools to read and update the user's private FocusWith projects, tasks, and timer. "
            "Read context before making recommendations. Only mark tasks complete when the user says they are done."
        ),
        json_response=True,
        **kwargs,
    )

    @server.tool(annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ))
    def get_focus_context() -> dict:
        """Read the active timer, open projects, today's tasks, and daily/weekly statistics."""
        return _call("get_focus_context")

    @server.tool(annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ))
    def create_project(title: str, outcome: str = "", weekly_target_minutes: int = 0) -> dict:
        """Create a project for a concrete outcome."""
        return _call("create_project", {
            "title": title,
            "outcome": outcome,
            "weekly_target_minutes": weekly_target_minutes,
        })

    @server.tool(annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ))
    def create_task(
        title: str,
        details: str = "",
        project_id: Optional[int] = None,
        estimated_minutes: int = 25,
        target_date: str = "",
        priority: int = 3,
    ) -> dict:
        """Create one actionable focus task, optionally inside a project."""
        arguments = {
            "title": title,
            "details": details,
            "project_id": project_id,
            "estimated_minutes": estimated_minutes,
            "priority": priority,
        }
        if target_date:
            arguments["target_date"] = target_date
        return _call("create_task", arguments)

    @server.tool(annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    ))
    def update_task(
        task_id: int,
        title: Optional[str] = None,
        details: Optional[str] = None,
        project_id: Optional[int] = None,
        estimated_minutes: Optional[int] = None,
        target_date: Optional[str] = None,
        priority: Optional[int] = None,
    ) -> dict:
        """Move, reschedule, rename, or reprioritize an existing task."""
        arguments = {"task_id": task_id}
        for key, value in {
            "title": title,
            "details": details,
            "project_id": project_id,
            "estimated_minutes": estimated_minutes,
            "target_date": target_date,
            "priority": priority,
        }.items():
            if value is not None:
                arguments[key] = value
        return _call("update_task", arguments)

    @server.tool(annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ))
    def start_focus(
        task_id: Optional[int] = None,
        title: str = "Free focus",
        minutes: int = 25,
        mode: Literal["pomodoro", "deep", "countup"] = "pomodoro",
    ) -> dict:
        """Start a timer for a task, or a named free-focus session."""
        return _call("start_focus", {"task_id": task_id, "title": title, "minutes": minutes, "mode": mode})

    @server.tool(annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    ))
    def control_focus(action: Literal["pause", "resume", "complete", "cancel"]) -> dict:
        """Pause, resume, complete, or cancel the current focus session."""
        return _call("control_focus", {"action": action})

    @server.tool(annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=True,
        openWorldHint=False,
    ))
    def complete_task(task_id: int) -> dict:
        """Mark a task complete after the user says it is done."""
        return _call("complete_task", {"task_id": task_id})

    return server


mcp = create_focus_mcp()


def run() -> None:
    # Stdio keeps the MCP server private and works with Claude Desktop, Claude Code,
    # Codex, and other local MCP clients. Remote HTTP needs a real OAuth deployment.
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run()
