"""Auth-aware async git clone — supports SSH key, SSH agent, HTTPS+creds, public HTTPS."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from workclaw.projects.models import AuthMethod, RepoSource

logger = logging.getLogger(__name__)


@dataclass
class CloneResult:
    """Result of a git clone operation."""

    success: bool
    path: Path | None = None
    error: str | None = None


def _build_ssh_command_extra(source: RepoSource) -> str:
    """Build the GIT_SSH_COMMAND value for SSH-based auth."""
    key_path = source.ssh_key_path

    # Fallback resolution for ssh_key: explicit > id_ed25519 > id_rsa
    if source.auth_method == AuthMethod.SSH_KEY and not key_path:
        ed25519 = Path.home() / ".ssh" / "id_ed25519"
        rsa = Path.home() / ".ssh" / "id_rsa"
        if ed25519.exists():
            key_path = ed25519
        elif rsa.exists():
            key_path = rsa

    parts = ["ssh", "-o", "StrictHostKeyChecking=accept-new"]
    if key_path:
        parts.extend(["-i", str(key_path), "-o", "IdentitiesOnly=yes"])
    return " ".join(parts)


def _build_https_url_with_creds(source: RepoSource) -> str:
    """Insert username:password into an HTTPS URL."""
    parsed = urlparse(source.url)
    password = os.environ.get(source.password_env_var or "", "")
    if not password:
        raise ValueError(
            f"Password env var '{source.password_env_var}' is not set or empty"
        )
    username = source.username or ""
    netloc = f"{username}:{password}@{parsed.hostname}"
    if parsed.port:
        netloc += f":{parsed.port}"
    return parsed._replace(netloc=netloc).geturl()


def build_clone_command(source: RepoSource, destination: Path) -> tuple[list[str], dict[str, str]]:
    """Build the git clone command and extra environment variables.

    Returns (args, extra_env) where args is the command list and extra_env
    contains any environment variables to set (e.g., GIT_SSH_COMMAND).
    """
    args = ["git", "clone", "--depth", "1"]
    if source.branch:
        args.extend(["--branch", source.branch])

    url = source.url
    extra_env: dict[str, str] = {}

    if source.auth_method in (AuthMethod.SSH_KEY, AuthMethod.SSH_AGENT):
        extra_env["GIT_SSH_COMMAND"] = _build_ssh_command_extra(source)
    elif source.auth_method == AuthMethod.HTTPS_CREDENTIALS:
        url = _build_https_url_with_creds(source)
    # AuthMethod.HTTPS — no modification needed

    args.extend([url, str(destination)])
    return args, extra_env


async def clone_repo(
    source: RepoSource,
    destination: Path,
    timeout: int = 120,
) -> CloneResult:
    """Clone a repository using auth settings from the RepoSource.

    Uses shallow clone (--depth 1) for efficiency.
    """
    try:
        args, extra_env = build_clone_command(source, destination)
    except ValueError as e:
        return CloneResult(success=False, error=str(e))

    # Ensure parent directory exists
    destination.parent.mkdir(parents=True, exist_ok=True)

    # If destination already exists, skip clone (caller should handle reclone)
    if destination.exists():
        return CloneResult(success=True, path=destination)

    env = {**os.environ, **extra_env}

    logger.info(f"Cloning {source.url} -> {destination} (auth={source.auth_method.value})")

    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

        if proc.returncode == 0:
            logger.info(f"Clone succeeded: {source.url}")
            return CloneResult(success=True, path=destination)

        error_msg = stderr.decode(errors="replace").strip()
        logger.error(f"Clone failed ({source.url}): {error_msg}")
        return CloneResult(success=False, error=error_msg)

    except TimeoutError:
        logger.error(f"Clone timed out after {timeout}s: {source.url}")
        return CloneResult(success=False, error=f"Clone timed out after {timeout}s")
    except Exception as e:
        logger.error(f"Clone error ({source.url}): {e}")
        return CloneResult(success=False, error=str(e))
