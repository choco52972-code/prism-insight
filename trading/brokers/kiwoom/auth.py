# -*- coding: utf-8 -*-
"""
키움 증권 REST API 인증 클래스
"""

import asyncio
import json
import logging
import os
import time
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union

import httpx

# BaseAuth를 직접 정의하거나 mock으로 처리
# from trading.common.base_auth import BaseAuth

# BaseAuth 추상 클래스 직접 정의 (임시)
class BaseAuth:
    """인증 클래스 기본 추상 클래스"""
    def __init__(self, config=None):
        self.config = config or {}
        self._config_cache = config or {}
    
    def get_config(self, key, default=None):
        """설정값 가져오기"""
        return self._config_cache.get(key, default)

logger = logging.getLogger(__name__)

# KIS와 동일한 패턴으로 config 디렉토리 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
config_root = os.path.join(current_dir, "config")

try:
    # Store and manage app key, app secret, token, account number, etc., set to your own path and filename.
    # pip install PyYAML (package installation)
    with open(os.path.join(config_root, "kiwoom_config.yaml"), encoding="UTF-8") as f:
        _cfg = yaml.safe_load(f)
except FileNotFoundError:
    # 설정 파일이 없을 경우 기본값 사용
    _cfg = {
        "mode": "mock",
        "api_key": "",
        "api_secret": "",
        "default_account": "",
        "accounts": []
    }

# 전역 설정 상수
KIWOOM_DEFAULT_MODE = str(_cfg.get("mode", "mock"))
KIWOOM_DEFAULT_API_KEY = str(_cfg.get("api_key", ""))
KIWOOM_DEFAULT_API_SECRET = str(_cfg.get("api_secret", ""))
KIWOOM_DEFAULT_ACCOUNT = str(_cfg.get("default_account", ""))
KIWOOM_ACCOUNTS = _cfg.get("accounts", [])

# Create directory if it doesn't exist
os.makedirs(config_root, exist_ok=True)


class KiwoomAuth(BaseAuth):
    """
    키움 증권 REST API 인증을 담당하는 클래스
    
    - OAuth2 토큰 발급 및 관리 (자동 갱신)
    - 실전투자(Real) 및 모의투자(Simulation) 모드 지원
    - Rate Limiter 통합 (초당 5회 제한)
    - 비동기 처리 (httpx 사용)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Args:
            config: 브로커 설정
                - mode: "real" 또는 "mock" (기본값: YAML 파일에서 정의된 mode)
        """
        super().__init__(config)
        
        # 설정 파일에서 기본값을 가져오고, config로 오버라이드
        self.mode = self.get_config("mode", KIWOOM_DEFAULT_MODE).lower()
        self.config_root = config_root
        
        self._api_key: Optional[str] = None
        self._api_secret: Optional[str] = None
        self._base_url: str = ""
        self._authenticated: bool = False
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[float] = None
        
        # Rate Limiting 설정 (초당 5회 제한)
        self._rate_limiter = asyncio.Semaphore(5)
        self._last_request_time = 0.0
        self._min_interval = 0.2  # 200ms
        
        self._client: Optional[httpx.AsyncClient] = None
        self._token_lock = asyncio.Lock()
        
        logger.debug(f"KiwoomAuth 초기화: mode={self.mode}, config_root={config_root}")

    @property
    async def client(self) -> httpx.AsyncClient:
        """httpx 비동기 클라이언트 제공 (지연 초기화)"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    def _load_credentials(self) -> None:
        """
        YAML 설정 파일로부터 API Key 및 Secret 로드 (KIS 패턴)
        
        Raises:
            KeyError: 해당 모드의 설정이 없는 경우
        """
        try:
            # YAML 파일 로드
            config_path = os.path.join(self.config_root, "kiwoom_config.yaml")
            if not os.path.exists(config_path):
                # 기본값 사용
                self._api_key = KIWOOM_DEFAULT_API_KEY
                self._api_secret = KIWOOM_DEFAULT_API_SECRET
                logger.info(f"키움 설정 파일 없음, 기본값 사용: mode={self.mode}")
                return
                
            with open(config_path, 'r', encoding='utf-8') as f:
                current_cfg = yaml.safe_load(f)
                
            # API 키/시크릿 로드
            self._api_key = str(current_cfg.get("api_key", KIWOOM_DEFAULT_API_KEY))
            self._api_secret = str(current_cfg.get("api_secret", KIWOOM_DEFAULT_API_SECRET))
            
            # 베이스 URL 설정
            is_real = self.mode in ("real", "prod", "live")
            self._base_url = "https://api.kiwoom.com" if is_real else "https://mockapi.kiwoom.com"
            
            # 계정 정보 로드
            accounts_list = current_cfg.get("accounts", KIWOOM_ACCOUNTS)
            if accounts_list and len(accounts_list) > 0:
                # 모드에 따라 적절한 계정 찾기
                mode_accounts = [acc for acc in accounts_list if 
                                acc.get("mode", "mock").lower() == self.mode]
                if mode_accounts:
                    self._default_account = mode_accounts[0].get("account_no", "")
                else:
                    # 첫 번째 계정 사용
                    self._default_account = accounts_list[0].get("account_no", "")
            else:
                self._default_account = str(current_cfg.get("default_account", KIWOOM_DEFAULT_ACCOUNT))
                
            logger.info(f"키움 설정 로드 완료: mode={self.mode}, base_url={self._base_url}")
            
        except yaml.YAMLError as e:
            logger.error(f"설정 파일 파싱 오류 (YAML): {e}")
            raise
        except Exception as e:
            logger.error(f"설정 로드 중 상세 오류: {e}")
            raise
            
        except json.JSONDecodeError as e:
            logger.error(f"자격증명 파일 파싱 오류 (JSON): {e}")
            raise
        except Exception as e:
            logger.error(f"자격증명 로드 중 상세 오류: {e}")
            raise

    async def _wait_for_rate_limit(self):
        """키움 API 초당 요청 제한(5회) 준수를 위한 세마포어 및 간격 조절"""
        async with self._rate_limiter:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < self._min_interval:
                wait_time = self._min_interval - elapsed
                await asyncio.sleep(wait_time)
            self._last_request_time = asyncio.get_event_loop().time()

    async def authenticate(self) -> bool:
        """
        Kiwoom REST API 인증 수행 (OAuth2 토큰 획득)
        
        Returns:
            bool: 인증 성공 여부
        """
        async with self._token_lock:
            try:
                # 자격증명 미로드 시 로드 시도
                if not self._api_key:
                    self._load_credentials()
                
                logger.info(f"키움 API 인증 시도 중... (mode={self.mode})")
                
                await self._wait_for_rate_limit()
                
                url = f"{self._base_url}/oauth2/token"
                payload = {
                    "grant_type": "client_credentials",
                    "appkey": self._api_key,
                    "secretkey": self._api_secret
                }
                
                c = await self.client
                response = await c.post(url, json=payload)
                
                if response.status_code != 200:
                    logger.error(f"키움 인증 HTTP 오류: {response.status_code} {response.text}")
                    self._authenticated = False
                    return False
                    
                result = response.json()
                
                if result.get("return_code") != 0:
                    logger.error(f"키움 토큰 발급 API 실패: {result.get('return_msg')} (code={result.get('return_code')})")
                    self._authenticated = False
                    return False
                
                # 인증 성공 데이터 저장
                self._access_token = result.get("token")
                # 토큰 만료 시간: 1시간(3600초)이나 안전을 위해 3500초로 설정
                expires_in = int(result.get("expires_in", 3600))
                self._token_expiry = time.time() + min(expires_in, 3500)
                self._authenticated = True
                
                logger.info("키움 API 인증 성공 및 토큰 획득 완료")
                return True
                
            except Exception as e:
                logger.error(f"인증 처리 중 예외 발생: {e}", exc_info=True)
                self._authenticated = False
                return False

    async def refresh_token(self) -> bool:
        """
        토큰 갱신
        키움 REST API는 별도 Refresh Token 방식이 아니므로 재인증(authenticate) 수행
        
        Returns:
            bool: 갱신 성공 여부
        """
        logger.info("키움 토큰 만료 또는 수동 갱신 요청으로 재인증을 수행합니다.")
        return await self.authenticate()

    def get_access_token(self) -> Optional[str]:
        """
        현재 유효한 액세스 토큰 반환
        
        Returns:
            Optional[str]: 액세스 토큰 또는 None
        """
        if not self.is_authenticated():
            return None
        return self._access_token

    def is_authenticated(self) -> bool:
        """
        인증 상태 확인 (토큰 존재 여부 및 만료 시간 확인)
        
        Returns:
            bool: 인증 유효 여부
        """
        if not self._authenticated or not self._access_token:
            return False
            
        # 토큰 만료 여부 확인
        if self._token_expiry and time.time() >= self._token_expiry:
            logger.warning("키움 액세스 토큰이 만료되었습니다.")
            return False
            
        return True

    async def logout(self) -> bool:
        """
        로그아웃 처리 및 클라이언트 종료
        
        Returns:
            bool: 로그아웃 성공 여부
        """
        try:
            self._access_token = None
            self._token_expiry = None
            self._authenticated = False
            
            if self._client:
                await self._client.aclose()
                self._client = None
                
            logger.info("키움 인증 세션 로그아웃 및 클라이언트 종료 완료")
            return True
        except Exception as e:
            logger.error(f"로그아웃 처리 중 오류: {e}")
            return False

    async def ensure_authenticated(self) -> bool:
        """
        BaseAuth.ensure_authenticated 오버라이드
        인증 상태를 확인하고 필요시 토큰을 갱신하거나 새로 발급받습니다.
        """
        if self.is_authenticated():
            return True
            
        logger.debug("인증이 필요하거나 토큰이 만료되어 인증을 수행합니다.")
        return await self.authenticate()

    async def get_token(self) -> Optional[str]:
        """
        현재 액세스 토큰을 반환합니다. 토큰이 없으면 인증을 시도합니다.
        
        Returns:
            Optional[str]: 액세스 토큰 또는 None
        """
        try:
            if await self.ensure_authenticated():
                return self._access_token
            return None
        except Exception as e:
            logger.error(f"토큰 획득 실패: {e}")
            return None

    async def get_auth_headers(self) -> Dict[str, str]:
        """
        API 호출에 사용할 인증 헤더 반환
        
        Returns:
            Dict[str, str]: Authorization 헤더가 포함된 딕셔너리
        """
        if not await self.ensure_authenticated():
            logger.error("인증 헤더 생성 실패: 인증 세션을 확보할 수 없습니다.")
            return {}
            
        return {
            "Content-Type": "application/json;charset=UTF-8",
            "Authorization": f"Bearer {self._access_token}"
        }

    def get_default_account(self) -> Optional[str]:
        """
        기본 계좌 번호를 반환합니다.
        
        Returns:
            Optional[str]: 기본 계좌 번호 또는 None
        """
        # 설정에서 계좌 번호 가져오기
        account = self.get_config("account_no")
        if account:
            return account
        
        try:
            if hasattr(self, '_default_account') and self._default_account:
                return self._default_account
                
            # YAML 파일에서 직접 읽기
            config_path = os.path.join(self.config_root, "kiwoom_config.yaml")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    current_cfg = yaml.safe_load(f)
                    
                accounts_list = current_cfg.get("accounts", [])
                if accounts_list:
                    for acc in accounts_list:
                        acc_mode = acc.get("mode", "mock").lower()
                        if acc_mode == self.mode or (self.mode == "mock" and acc_mode == ""):
                            return acc.get("account_no", "")
                    
                    # 첫 번째 계정 사용
                    return accounts_list[0].get("account_no", "")
                else:
                    return current_cfg.get("default_account", "")
        except Exception as e:
            logger.debug(f"계좌 번호 YAML 조회 실패: {e}")
        
        logger.warning(f"기본 계좌 번호를 찾을 수 없습니다. mode={self.mode}")
        return None

    async def validate_token(self) -> bool:
        """
        현재 토큰의 유효성을 검증합니다.
        
        Returns:
            bool: 토큰 유효 여부
        """
        try:
            if not self._access_token:
                return False
            
            # 토큰 만료 시간 확인
            if self._token_expiry and self._token_expiry <= time.time():
                return False
            
            return True
        except Exception:
            return False
