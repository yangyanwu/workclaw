"""WorkClaw GUI — FastAPI server with WebSocket chat interface."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from workclaw import __app_name__, __version__
from workclaw.config.settings import get_settings
from workclaw.core.agent import EventType, WorkClawAgent
from workclaw.core.memory import Memory
from workclaw.llm.provider import LLMProvider
from workclaw.storage.store import FileStore
from workclaw.tools.file_ops import (
    ListDirectoryTool,
    ReadFileTool,
    SearchInFilesTool,
    WriteFileTool,
)
from workclaw.tools.git_ops import (
    GitBranchTool,
    GitCloneTool,
    GitCommitTool,
    GitDiffTool,
    GitPushTool,
    GitStatusTool,
)
from workclaw.tools.registry import ToolRegistry
from workclaw.tools.shell import ShellTool

logger = logging.getLogger(__name__)

# Static files directory
STATIC_DIR = Path(__file__).parent / "static"

# FastAPI app
app = FastAPI(
    title=__app_name__,
    version=__version__,
    description="AI-powered developer tool for Jira, GitHub, and Bitbucket",
)

# Serve static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _create_agent() -> WorkClawAgent:
    """Bootstrap the agent with all dependencies."""
    settings = get_settings()
    store = FileStore(settings.data_dir)
    memory = Memory(store)
    llm = LLMProvider(settings)

    registry = ToolRegistry()
    for tool_cls in [
        ReadFileTool,
        WriteFileTool,
        ListDirectoryTool,
        SearchInFilesTool,
        GitCloneTool,
        GitBranchTool,
        GitCommitTool,
        GitPushTool,
        GitDiffTool,
        GitStatusTool,
        ShellTool,
    ]:
        registry.register(tool_cls())

    return WorkClawAgent(settings, llm, registry, memory)


# --- HTTP Routes ---


@app.get("/")
async def index():
    """Serve the main chat page."""
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return JSONResponse(
        {
            "status": "ok",
            "app": __app_name__,
            "version": __version__,
        }
    )


@app.get("/api/conversations")
async def list_conversations():
    """List saved conversations."""
    settings = get_settings()
    store = FileStore(settings.data_dir)
    memory = Memory(store)
    conversations = memory.list_conversations()
    return JSONResponse({"conversations": conversations})


@app.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    """Delete a conversation."""
    settings = get_settings()
    store = FileStore(settings.data_dir)
    memory = Memory(store)
    deleted = memory.delete_conversation(conv_id)
    return JSONResponse({"deleted": deleted})


# --- WebSocket Chat ---


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for real-time chat with the agent."""
    await websocket.accept()
    agent = _create_agent()

    try:
        while True:
            # Receive message from client
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = {"message": raw}

            message = data.get("message", "")
            conv_id = data.get("conversation_id")
            action = data.get("action", "chat")

            # Handle actions
            if action == "new_conversation":
                conv = agent.new_conversation()
                await websocket.send_json(
                    {
                        "type": "conversation_created",
                        "conversation_id": conv.id,
                        "title": conv.title,
                    }
                )
                continue

            if action == "load_conversation":
                if conv_id:
                    conv = agent.load_conversation(conv_id)
                    if conv:
                        # Send conversation history
                        history = []
                        for msg in conv.messages:
                            if msg["role"] in ("user", "assistant"):
                                history.append(
                                    {
                                        "role": msg["role"],
                                        "content": msg.get("content", ""),
                                    }
                                )
                        await websocket.send_json(
                            {
                                "type": "conversation_loaded",
                                "conversation_id": conv.id,
                                "title": conv.title,
                                "history": history,
                            }
                        )
                    else:
                        await websocket.send_json(
                            {"type": "error", "message": "Conversation not found"}
                        )
                continue

            if not message:
                continue

            # Ensure we have an active conversation
            if not agent.conversation:
                if conv_id:
                    agent.load_conversation(conv_id)
                if not agent.conversation:
                    agent.new_conversation()

            # Stream agent events to client
            async for event in agent.run(message):
                payload: dict[str, Any] = {"type": event.type.value}

                if event.type == EventType.STATUS:
                    payload["message"] = event.data.get("message", "")

                elif event.type == EventType.TOOL_CALL:
                    payload["tool"] = event.data.get("tool", "")
                    payload["arguments"] = event.data.get("arguments", {})

                elif event.type == EventType.TOOL_RESULT:
                    payload["tool"] = event.data.get("tool", "")
                    payload["output"] = event.data.get("output", "")[:2000]

                elif event.type == EventType.RESPONSE:
                    payload["content"] = event.data.get("content", "")
                    payload["usage"] = event.data.get("usage", {})
                    payload["model"] = event.data.get("model", "")
                    payload["conversation_id"] = (
                        agent.conversation.id if agent.conversation else ""
                    )
                    payload["conversation_title"] = (
                        agent.conversation.title if agent.conversation else ""
                    )

                elif event.type == EventType.ERROR:
                    payload["message"] = event.data.get("message", "")

                await websocket.send_json(payload)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json(
                {"type": "error", "message": str(e)}
            )
        except Exception:
            pass


def run():
    """Run the GUI server."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "workclaw.gui.server:app",
        host=settings.gui_host,
        port=settings.gui_port,
        reload=True,
    )
