import os
from pathlib import Path

# OAuth PKCE configuration (mirrors Claude Code)
OAUTH_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
OAUTH_AUTHORIZE_URL = "https://claude.com/cai/oauth/authorize"
OAUTH_TOKEN_URL = "https://platform.claude.com/v1/oauth/token"
# Full scope list extracted from Claude Code binary (Jy8 constant)
OAUTH_SCOPE = "org:create_api_key user:profile user:inference user:sessions:claude_code user:mcp_servers user:file_upload"

# Proxy Server configuration
DEFAULT_PROXY_PORT = int(os.getenv("PRISM_CLAUDE_PROXY_PORT", "18742"))
CLAUDE_BASE_URL = "https://api.anthropic.com"

# Auth storage
AUTH_DIR = Path.home() / ".prism" / "auth"
AUTH_FILE = AUTH_DIR / "claude_oauth.json"

# Loopback callback — Anthropic follows RFC 8252, any port is accepted
OAUTH_CALLBACK_PORT = 54545
OAUTH_REDIRECT_URI = f"http://localhost:{OAUTH_CALLBACK_PORT}/callback"
