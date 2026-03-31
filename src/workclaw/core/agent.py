"""WorkClaw Agent — the ReAct loop that orchestrates reasoning and tool use."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncGenerator, Optional

from workclaw.config.settings import WorkClawSettings
from workclaw.core.context import ContextAssembler
from workclaw.core.memory import Memory
from workclaw.llm.prompts import SYSTEM_PROMPT
from workclaw.llm.provider import LLMProvider
from workclaw.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of events emitted by the agent."""

    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    RESPONSE = "response"
    ERROR = "error"
    STATUS = "status"


@dataclass
class AgentEvent:
    """An event emitted during agent execution."""

    type: EventType
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class Conversation:
    """Represents a chat conversation with history."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = "New Conversation"
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class WorkClawAgent:
    """The core agent that orchestrates the ReAct loop.

    Flow: User message → assemble context → LLM call → parse response →
          if tool_call: execute tool → feed result back → repeat
          if text: return response to user
    """

    def __init__(
        self,
        settings: WorkClawSettings,
        llm: LLMProvider,
        tool_registry: ToolRegistry,
        memory: Memory,
    ) -> None:
        self.settings = settings
        self.llm = llm
        self.tools = tool_registry
        self.memory = memory
        self.context = ContextAssembler(settings)
        self.conversation: Optional[Conversation] = None
        self.project_context: Optional[str] = None

    def new_conversation(self, title: str = "New Conversation") -> Conversation:
        """Start a new conversation."""
        self.conversation = Conversation(title=title)
        return self.conversation

    def load_conversation(self, conv_id: str) -> Optional[Conversation]:
        """Load a previous conversation from storage."""
        data = self.memory.load_conversation(conv_id)
        if data:
            self.conversation = Conversation(
                id=data["id"],
                title=data.get("title", "Untitled"),
                messages=data.get("messages", []),
                created_at=data.get("created_at", ""),
            )
            return self.conversation
        return None

    def set_project_context(self, project_name: str) -> None:
        """Load project analysis markdown from FileStore and set as context."""
        md = self.memory.store.load_markdown("project_analysis", f"{project_name}_analysis")
        if md:
            self.project_context = md
            logger.info(f"Loaded project context for: {project_name}")
        else:
            logger.warning(f"No analysis found for project: {project_name}")
            self.project_context = None

    def clear_project_context(self) -> None:
        """Remove project context from the agent."""
        self.project_context = None

    async def run(self, user_message: str) -> AsyncGenerator[AgentEvent, None]:
        """Process a user message through the ReAct loop.

        Yields AgentEvents as the agent thinks, calls tools, and responds.
        """
        if not self.conversation:
            self.new_conversation()

        # Add user message to history
        self.conversation.messages.append(
            {"role": "user", "content": user_message}
        )

        # Auto-title from first message
        if len(self.conversation.messages) == 1:
            self.conversation.title = user_message[:80]

        yield AgentEvent(type=EventType.STATUS, data={"message": "Thinking..."})

        iteration = 0
        max_iterations = self.settings.agent_max_iterations

        while iteration < max_iterations:
            iteration += 1

            # Assemble context
            messages = self.context.build_messages(
                system_prompt=SYSTEM_PROMPT,
                conversation_messages=self.conversation.messages,
                memory_context=self.memory.get_relevant_context(user_message),
                project_context=self.project_context,
            )

            # Get tool definitions
            tools = self.tools.to_openai_tools() if len(self.tools) > 0 else None

            # Call LLM
            try:
                response = await self.llm.achat(
                    messages=messages,
                    tools=tools,
                )
            except Exception as e:
                yield AgentEvent(
                    type=EventType.ERROR,
                    data={"message": f"LLM call failed: {str(e)}"},
                )
                return

            # Handle tool calls
            if response.tool_calls:
                # Add assistant message with tool calls to history
                self.conversation.messages.append(
                    {
                        "role": "assistant",
                        "content": response.content or "",
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": json.dumps(tc["arguments"]),
                                },
                            }
                            for tc in response.tool_calls
                        ],
                    }
                )

                # Execute each tool call
                for tc in response.tool_calls:
                    yield AgentEvent(
                        type=EventType.TOOL_CALL,
                        data={
                            "tool": tc["name"],
                            "arguments": tc["arguments"],
                            "id": tc["id"],
                        },
                    )

                    # Execute the tool
                    tool = self.tools.get(tc["name"])
                    if tool:
                        try:
                            result = await tool.execute(**tc["arguments"])
                            tool_output = result.output if result.success else f"Error: {result.error}"
                        except Exception as e:
                            tool_output = f"Tool execution error: {str(e)}"
                    else:
                        tool_output = f"Unknown tool: {tc['name']}"

                    yield AgentEvent(
                        type=EventType.TOOL_RESULT,
                        data={
                            "tool": tc["name"],
                            "id": tc["id"],
                            "output": tool_output[:2000],  # Truncate for display
                            "success": tool.name if tool else False,
                        },
                    )

                    # Add tool result to conversation
                    self.conversation.messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": tool_output,
                        }
                    )

                # Continue the loop — LLM needs to process tool results
                continue

            # No tool calls — this is the final response
            assistant_message = response.content or ""
            self.conversation.messages.append(
                {"role": "assistant", "content": assistant_message}
            )

            yield AgentEvent(
                type=EventType.RESPONSE,
                data={
                    "content": assistant_message,
                    "usage": response.usage,
                    "model": response.model,
                },
            )

            # Save conversation
            self._save_conversation()
            return

        # Hit max iterations
        yield AgentEvent(
            type=EventType.ERROR,
            data={
                "message": f"Agent reached maximum iterations ({max_iterations}). "
                "The task may be too complex for a single request."
            },
        )
        self._save_conversation()

    def _save_conversation(self) -> None:
        """Persist the current conversation."""
        if self.conversation:
            self.memory.save_conversation(
                self.conversation.id,
                {
                    "id": self.conversation.id,
                    "title": self.conversation.title,
                    "messages": self.conversation.messages,
                    "created_at": self.conversation.created_at,
                },
            )

    def list_conversations(self) -> list[dict[str, str]]:
        """List saved conversations."""
        return self.memory.list_conversations()
