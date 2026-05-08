"""Claude OAuth Token Manager.

Handles token persistence, validation, and automatic refresh.
"""

import json
import logging
import time

import aiohttp

from .constants import (
    AUTH_FILE,
    OAUTH_CLIENT_ID,
    OAUTH_SCOPE,
    OAUTH_TOKEN_URL,
)

logger = logging.getLogger(__name__)


class TokenManager:
    """Manages Claude OAuth tokens with auto-refresh."""

    def __init__(self):
        self._auth_data = None

    def _load_auth(self) -> dict:
        """Load auth data from disk."""
        if not AUTH_FILE.exists():
            raise RuntimeError(
                f"Authentication file not found at {AUTH_FILE}. "
                "Run 'python -m cores.claude_proxy.oauth_login' to authenticate."
            )

        try:
            with open(AUTH_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            raise RuntimeError(f"Failed to read auth file: {e}")

    async def get_token(self) -> str:
        """Get a valid access token, refreshing if necessary."""
        if not self._auth_data:
            self._auth_data = self._load_auth()

        now = int(time.time())
        # Refresh if expires in less than 5 minutes
        if self._auth_data.get("expires_at", 0) < now + 300:
            logger.info("Claude token expired or expiring soon, refreshing...")
            await self.refresh_token()

        return self._auth_data["access_token"]

    async def refresh_token(self) -> None:
        """Refresh the access token using the refresh token."""
        refresh_token = self._auth_data.get("refresh_token")
        if not refresh_token:
            raise RuntimeError(
                "No refresh token available. "
                "Run 'python -m cores.claude_proxy.oauth_login' to re-authenticate."
            )

        token_data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": OAUTH_CLIENT_ID,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                OAUTH_TOKEN_URL,
                json=token_data,
                headers={"Content-Type": "application/json"},
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error("Claude token refresh failed (%d): %s", resp.status, body)
                    raise RuntimeError(
                        f"Token refresh failed ({resp.status}). "
                        "Run 'python -m cores.claude_proxy.oauth_login' to re-authenticate."
                    )
                tokens = await resp.json()

        # Update auth data
        expires_in = tokens.get("expires_in", 3600)
        self._auth_data.update({
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token", refresh_token),
            "expires_at": int(time.time()) + expires_in,
        })

        # Save back to disk
        from .oauth_login import _save_auth
        _save_auth(self._auth_data)
        logger.info("Claude token refreshed successfully")

    def validate_or_fail(self) -> None:
        """Quick check if we have any auth data at all."""
        if not AUTH_FILE.exists():
            raise RuntimeError(
                f"Not authenticated. Run 'python -m cores.claude_proxy.oauth_login' to login."
            )
