"""
KIS Broker Authentication
Implements BaseAuth abstract interface and exposes the full KisAuth legacy API.
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from trading.common.base_auth import BaseAuth

logger = logging.getLogger(__name__)


def _get_ka():
    """Return the real kis_auth module."""
    from trading.brokers.kis import kis_auth as ka
    return ka


@dataclass
class KISAccount:
    """KIS 계좌 정보"""
    account_no: str
    account_type: str = "일반"
    nickname: str = ""
    main: bool = False
    broker: str = "kis"


class KISAuth(BaseAuth):
    """KIS 브로커 인증"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config or {})
        self._ka = _get_ka()
        self._svr = self.get_config("svr", "vps")
        self._product = self.get_config("product", "01")
        env = self._ka.getEnv()
        self.mode = str(env.get("default_mode", "demo")).lower()
        logger.info(f"KISAuth initialized: mode={self.mode}")

    # ── BaseAuth abstract methods ─────────────────────────────────────────

    async def authenticate(self) -> bool:
        try:
            self._ka.auth(svr=self._svr, product=self._product)
            return True
        except Exception as e:
            logger.error(f"authenticate failed: {e}")
            return False

    async def refresh_token(self) -> bool:
        try:
            self._ka.reAuth(svr=self._svr, product=self._product)
            return True
        except Exception as e:
            logger.error(f"refresh_token failed: {e}")
            return False

    def get_access_token(self) -> Optional[str]:
        try:
            env = self._ka.getTREnv()
            return env.my_token if env else None
        except Exception:
            return None

    def is_authenticated(self) -> bool:
        try:
            return self._ka.getTREnv() is not None
        except Exception:
            return False

    async def logout(self) -> bool:
        return True

    # ── Token helpers ─────────────────────────────────────────────────────

    async def get_token(self, account_key: Optional[str] = None) -> str:
        return self._ka.read_token(account_key=account_key) or ""

    async def save_token(self, token: str, expired: str,
                         account_key: Optional[str] = None) -> None:
        self._ka.save_token(token, expired, account_key=account_key)

    async def validate_token(self) -> bool:
        return True

    # ── Account / env helpers ─────────────────────────────────────────────

    def get_default_account(self) -> Optional[str]:
        env = self._ka.getEnv()
        for acc in env.get("accounts", []):
            if acc.get("is_primary") or acc.get("primary"):
                return acc.get("account_no")
        accounts = env.get("accounts", [])
        return accounts[0].get("account_no") if accounts else None

    def get_config_root(self) -> str:
        return str(self._ka.config_root)

    def is_real_mode(self) -> bool:
        return self.mode in ("real", "prod")

    def get_accounts(self) -> List[KISAccount]:
        accounts = []
        for acc in self._ka.getEnv().get("accounts", []):
            accounts.append(KISAccount(
                account_no=acc.get("account_no", ""),
                account_type=acc.get("account_type", "일반"),
                nickname=acc.get("name", ""),
                main=bool(acc.get("is_primary") or acc.get("primary")),
            ))
        return accounts


class KisAuth(KISAuth):
    """
    Backward-compatible alias.
    Callers using `ka = KisAuth(...)` or `from trading.brokers.kis.auth import KisAuth as ka`
    can call ka.getEnv(), ka.get_configured_accounts(), ka.changeTREnv(), etc.
    """

    @staticmethod
    def getEnv() -> Dict[str, Any]:
        return _get_ka().getEnv()

    @staticmethod
    def get_configured_accounts(svr=None, product=None, market=None,
                                primary_only=False) -> list:
        return _get_ka().get_configured_accounts(
            svr=svr, product=product, market=market, primary_only=primary_only,
        )

    @staticmethod
    def resolve_account(svr, product=None, account_name=None, account_index=None,
                        market=None, account_key=None) -> dict:
        return _get_ka().resolve_account(
            svr=svr, product=product, account_name=account_name,
            account_index=account_index, market=market, account_key=account_key,
        )

    @staticmethod
    def mask_account_number(account_number) -> str:
        return _get_ka().mask_account_number(account_number)

    @staticmethod
    def changeTREnv(token_key, svr="prod", product=None, account_name=None,
                    account_index=None, account_key=None) -> None:
        from trading.brokers.kis.kis_auth import DEFAULT_PRODUCT_CODE
        return _get_ka().changeTREnv(
            token_key, svr=svr, product=product or DEFAULT_PRODUCT_CODE,
            account_name=account_name, account_index=account_index,
            account_key=account_key,
        )

    @staticmethod
    def getTREnv():
        return _get_ka().getTREnv()

    @staticmethod
    def get_trading_env_lock():
        return _get_ka().get_trading_env_lock()

    @staticmethod
    def _url_fetch(api_url, ptr_id, tr_cont, params, appendHeaders=None,
                   postFlag=False, hashFlag=True):
        return _get_ka()._url_fetch(
            api_url, ptr_id, tr_cont, params,
            appendHeaders=appendHeaders, postFlag=postFlag, hashFlag=hashFlag,
        )

    @staticmethod
    def auth(svr="prod", product=None, url=None, account_name=None,
             account_index=None, account_key=None) -> None:
        from trading.brokers.kis.kis_auth import DEFAULT_PRODUCT_CODE
        return _get_ka().auth(
            svr=svr, product=product or DEFAULT_PRODUCT_CODE, url=url,
            account_name=account_name, account_index=account_index,
            account_key=account_key,
        )

    @staticmethod
    def reAuth(svr="prod", product=None, account_name=None,
               account_index=None, account_key=None) -> None:
        from trading.brokers.kis.kis_auth import DEFAULT_PRODUCT_CODE
        return _get_ka().reAuth(
            svr=svr, product=product or DEFAULT_PRODUCT_CODE,
            account_name=account_name, account_index=account_index,
            account_key=account_key,
        )

    @staticmethod
    def isPaperTrading() -> bool:
        return _get_ka().isPaperTrading()

    @staticmethod
    def smart_sleep() -> None:
        return _get_ka().smart_sleep()


# Lazily re-export exception/response types so callers can do:
#   from trading.brokers.kis.auth import KISAuthError
def __getattr__(name: str):
    _re_exports = {
        "KISAuthError", "TokenFileError", "CredentialMismatchError",
        "TokenRequestError", "SecurityError", "APIResp", "APIRespError",
        "KISEnv", "CrossPlatformFileLock", "KISWebSocket",
    }
    if name in _re_exports:
        return getattr(_get_ka(), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
