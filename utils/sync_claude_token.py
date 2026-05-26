#!/usr/bin/env python3
"""
sync_claude_token.py
Claude Code OAuth 토큰을 mcp_agent.secrets.yaml에 자동 동기화

동작:
1. ~/.claude/.credentials.json 에서 accessToken / expiresAt 읽기
2. 만료 임박(30분 이내)이면 refreshToken으로 토큰 갱신
3. ~/.claude/.credentials.json 업데이트 (새 토큰 저장)
4. mcp_agent.secrets.yaml 의 anthropic.api_key 교체
5. 성공/실패 여부를 logs/sync_token.log 에 기록

사용법:
    python3 utils/sync_claude_token.py              # 일반 실행
    python3 utils/sync_claude_token.py --force      # 만료 여부 무관하게 강제 동기화
    python3 utils/sync_claude_token.py --dry-run    # 실제 파일은 수정하지 않고 상태만 출력

Cron 예시 (6시간마다):
    0 */6 * * * cd /home/leedw/projects/prism-insight && \
        /home/leedw/projects/prism-insight/venv/bin/python3 utils/sync_claude_token.py \
        >> logs/sync_token.log 2>&1
"""

import argparse
import json
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# ──────────────────────────────────────────────
# 경로 설정
# ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"
SECRETS_PATH = PROJECT_ROOT / "mcp_agent.secrets.yaml"
LOG_PATH = PROJECT_ROOT / "logs" / "sync_token.log"

# ──────────────────────────────────────────────
# Claude Code OAuth 상수
# ──────────────────────────────────────────────
OAUTH_CLIENT_ID = "https://claude.ai/oauth/claude-code-client-metadata"
TOKEN_ENDPOINT = "https://platform.claude.com/v1/oauth/token"
EXPIRE_BUFFER_SEC = 30 * 60  # 만료 30분 전부터 갱신 시도

# ──────────────────────────────────────────────
# 로거
# ──────────────────────────────────────────────
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 자격증명 읽기 / 쓰기
# ──────────────────────────────────────────────

def load_credentials() -> dict:
    """~/.claude/.credentials.json 에서 claudeAiOauth 섹션을 읽습니다."""
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(f"credentials 파일 없음: {CREDENTIALS_PATH}")
    with open(CREDENTIALS_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    creds = raw.get("claudeAiOauth")
    if not creds:
        raise KeyError("credentials.json 에 'claudeAiOauth' 키가 없습니다.")
    return creds


def save_credentials(creds: dict) -> None:
    """갱신된 토큰을 ~/.claude/.credentials.json 에 저장합니다."""
    with open(CREDENTIALS_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    raw["claudeAiOauth"] = creds
    with open(CREDENTIALS_PATH, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)
    logger.info("credentials.json 업데이트 완료")


# ──────────────────────────────────────────────
# 토큰 상태 확인
# ──────────────────────────────────────────────

def is_expiring_soon(creds: dict) -> bool:
    """accessToken 이 EXPIRE_BUFFER_SEC 이내에 만료되면 True."""
    expires_at_ms = creds.get("expiresAt", 0)
    expires_at_sec = expires_at_ms / 1000
    remaining = expires_at_sec - time.time()
    expires_dt = datetime.fromtimestamp(expires_at_sec).strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"토큰 만료시각: {expires_dt} (남은시간: {int(remaining // 60)}분 {int(remaining % 60)}초)")
    return remaining < EXPIRE_BUFFER_SEC


# ──────────────────────────────────────────────
# 토큰 갱신
# ──────────────────────────────────────────────

def refresh_access_token(refresh_token: str) -> dict:
    """
    platform.claude.com/v1/oauth/token 으로 새 accessToken 을 발급받습니다.

    Returns:
        {"access_token": ..., "refresh_token": ..., "expires_in": ...} 형태의 응답
    """
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": OAUTH_CLIENT_ID,
    }
    resp = requests.post(
        TOKEN_ENDPOINT,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"토큰 갱신 실패 (HTTP {resp.status_code}): {resp.text[:200]}"
        )
    return resp.json()


def apply_refreshed_token(creds: dict, token_resp: dict) -> dict:
    """refresh 응답을 기존 creds 에 병합해 새 creds 반환."""
    new_creds = dict(creds)
    new_creds["accessToken"] = token_resp["access_token"]
    # refresh_token 이 응답에 포함된 경우 교체 (rotation)
    if "refresh_token" in token_resp:
        new_creds["refreshToken"] = token_resp["refresh_token"]
    if "expires_in" in token_resp:
        new_creds["expiresAt"] = int((time.time() + token_resp["expires_in"]) * 1000)
    return new_creds


# ──────────────────────────────────────────────
# secrets.yaml 업데이트
# ──────────────────────────────────────────────

def update_secrets_yaml(api_key: str, dry_run: bool = False) -> None:
    """
    mcp_agent.secrets.yaml 의 anthropic.api_key 를 교체합니다.
    주석과 $schema 줄은 그대로 보존합니다.
    """
    if not SECRETS_PATH.exists():
        raise FileNotFoundError(f"secrets 파일 없음: {SECRETS_PATH}")

    content = SECRETS_PATH.read_text(encoding="utf-8")

    # anthropic: 블록 내의 api_key: 값을 교체 (정규식)
    pattern = r"(anthropic:\s*\n\s*api_key:\s*)(\S+)"
    replacement = rf"\g<1>{api_key}"
    new_content, count = re.subn(pattern, replacement, content)

    if count == 0:
        raise ValueError(
            "mcp_agent.secrets.yaml 에서 'anthropic.api_key' 패턴을 찾지 못했습니다."
        )

    if dry_run:
        logger.info("[DRY-RUN] secrets.yaml 을 수정하지 않습니다 (변경 예정 확인 완료)")
        return

    SECRETS_PATH.write_text(new_content, encoding="utf-8")
    logger.info("mcp_agent.secrets.yaml → anthropic.api_key 업데이트 완료")


# ──────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Claude Code OAuth 토큰을 mcp_agent.secrets.yaml 에 동기화"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="만료 여부와 관계없이 강제로 동기화"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="실제 파일은 변경하지 않고 상태만 출력"
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Claude Token 동기화 시작")

    try:
        creds = load_credentials()
        access_token = creds["accessToken"]
        refresh_token = creds.get("refreshToken", "")

        need_refresh = args.force or is_expiring_soon(creds)

        if need_refresh:
            if not refresh_token:
                logger.error("refreshToken 이 없어 갱신 불가. 수동 재로그인이 필요합니다.")
                return 1

            logger.info("토큰 갱신 중 → platform.claude.com/v1/oauth/token")
            try:
                token_resp = refresh_access_token(refresh_token)
                creds = apply_refreshed_token(creds, token_resp)
                access_token = creds["accessToken"]
                if not args.dry_run:
                    save_credentials(creds)
                logger.info("토큰 갱신 성공")
            except Exception as e:
                logger.warning(f"토큰 갱신 실패 ({e}), 기존 토큰으로 계속 진행")
                # 갱신 실패해도 현재 토큰이 아직 유효하면 그대로 사용
        else:
            logger.info("토큰이 충분히 유효합니다. 갱신 불필요")

        # secrets.yaml 동기화
        update_secrets_yaml(access_token, dry_run=args.dry_run)

        token_preview = access_token[:20] + "..." if len(access_token) > 20 else access_token
        logger.info(f"동기화 완료 ✅  (token: {token_preview})")
        return 0

    except Exception as e:
        logger.error(f"동기화 실패: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
