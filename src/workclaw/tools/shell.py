"""Shell command execution tool with timeout and safety constraints."""

from __future__ import annotations

import asyncio
import logging
import subprocess
from typing import Any

from workclaw.tools.base import Tool, ToolResult

logger = logging.getLogger(__name__)

# Commands that are never allowed
BLOCKED_COMMANDS = {
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "dd if=",
    ":(){:|:&};:",
    "shutdown",
    "reboot",
    "halt",
}


class ShellTool(Tool):
    """Execute shell commands with safety constraints."""

    name = "run_command"
    description = (
        "Execute a shell command and return its output. "
        "Use for building, testing, running scripts, or inspecting the system. "
        "Commands have a timeout and dangerous commands are blocked."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute",
            },
            "cwd": {
                "type": "string",
                "description": "Working directory for the command (optional)",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default: 60, max: 300)",
            },
        },
        "required": ["command"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        command = kwargs["command"]
        cwd = kwargs.get("cwd")
        timeout = min(kwargs.get("timeout", 60), 300)

        # Safety check
        cmd_lower = command.lower().strip()
        for blocked in BLOCKED_COMMANDS:
            if blocked in cmd_lower:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Command blocked for safety: contains '{blocked}'",
                )

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            stdout_text = stdout.decode("utf-8", errors="replace").strip()
            stderr_text = stderr.decode("utf-8", errors="replace").strip()

            # Truncate very long output
            max_output = 10000
            if len(stdout_text) > max_output:
                stdout_text = stdout_text[:max_output] + f"\n\n... (truncated, {len(stdout_text)} total chars)"

            if process.returncode != 0:
                combined = f"STDOUT:\n{stdout_text}\n\nSTDERR:\n{stderr_text}" if stdout_text else stderr_text
                return ToolResult(
                    success=False,
                    output=combined,
                    error=f"Command exited with code {process.returncode}",
                )

            output = stdout_text
            if stderr_text:
                output += f"\n\nSTDERR:\n{stderr_text}"

            return ToolResult(success=True, output=output or "(no output)")
        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                output="",
                error=f"Command timed out after {timeout}s",
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
