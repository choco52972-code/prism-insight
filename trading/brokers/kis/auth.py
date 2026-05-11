"""
KIS Broker Authentication (설정 기반)
- Mock 모드: 내부 Mock 사용
- Real 모드: 외부 kis_auth 패키지 필요
"""

import os
import yaml
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

from trading.common.base_auth import BaseAuth

logger = logging.getLogger(__name__)


@dataclass
class KISAccount:
    """KIS 계좌 정보"""
    account_no: str
    account_type: str = "일반"
    nickname: str = ""
    main: bool = False
    broker: str = "kis"


class KISConfig:
    """KIS 설정 관리 클래스"""
    
    def __init__(self, config_root: str = ""):
        self.config_root = config_root or self._get_default_config_root()
        self.config_path = Path(self.config_root) / "kis_config.yaml"
        self.config = self.load_config()
        logger.info(f"KIS 설정 로드: {self.config_path}")
    
    def _get_default_config_root(self) -> str:
        """기본 설정 디렉토리 경로"""
        current_dir = Path(__file__).parent
        config_dir = current_dir / "config"
        if not config_dir.exists():
            config_dir.mkdir(parents=True, exist_ok=True)
        return str(config_dir)
    
    def load_config(self) -> Dict[str, Any]:
        """YAML 설정 파일 로드"""
        if not self.config_path.exists():
            logger.warning(f"KIS 설정 파일 없음: {self.config_path}")
            return self.get_default_config()
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # 기본값과 병합
            default_config = self.get_default_config()
            merged = {**default_config, **config} if config else default_config
            logger.debug(f"KIS 설정 로드 완료: mode={merged.get('mode', 'N/A')}")
            return merged
            
        except Exception as e:
            logger.error(f"KIS 설정 파일 로드 실패: {e}")
            return self.get_default_config()
    
    def get_default_config(self) -> Dict[str, Any]:
        """기본 설정 반환"""
        return {
            "mode": "mock",
            "api_key": "",
            "secret_key": "",
            "app_name": "Prism Insight KIS",
            "default_account": "",
            "accounts": [],
            "api_config": {
                "base_url": "https://openapi.koreainvestment.com:9443",
                "oauth_url": "https://openapivts.koreainvestment.com:29443",
                "timeout": 30,
                "max_retries": 3
            },
            "mock_config": {
                "initial_balance": 100000000,
                "stock_count": 50,
                "price_variation_pct": 3.0,
                "trade_success_rate": 0.95
            }
        }
    
    def get_accounts(self) -> List[KISAccount]:
        """계좌 목록 가져오기"""
        accounts = []
        for acc_data in self.config.get("accounts", []):
            accounts.append(KISAccount(**acc_data))
        return accounts
    
    def get_default_account(self) -> Optional[str]:
        """기본 계좌 번호 가져오기"""
        accounts = self.get_accounts()
        for acc in accounts:
            if acc.main:
                return acc.account_no
        return accounts[0].account_no if accounts else None


class KISAuth(BaseAuth):
    """KIS 브로커 인증 클래스 (설정 기반)"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        # 설정 로드
        self.config_loader = KISConfig(
            config_root=self.get_config("config_root", "")
        )
        self.config = self.config_loader.config
        self.mode = self.config.get("mode", "mock")
        
        # Provider 초기화
        self._init_providers()
        
        logger.info(f"KISAuth 초기화: mode={self.mode}")
    
    def _init_providers(self):
        """모드에 따라 Provider 초기화"""
        if self.mode == "real":
            # 실제 KIS 사용 (kis_auth 패키지 필요)
            self._init_real_provider()
        else:
            # Mock Provider 사용
            self._init_mock_provider()
    
    def _init_real_provider(self):
        """실제 KIS provider 초기화"""
        try:
            import kis_auth as ka
            from kis_auth import KISTokenProvider, KISAccountProvider
            
            # Config 경로 설정
            config_path = self.config_loader.config_root
            
            # Provider 생성
            self.token_provider = KISTokenProvider(config_path, env="devlp")
            self.account_provider = KISAccountProvider(config_path, env="devlp")
            
            logger.info("실제 KIS provider 초기화 완료")
            self._has_real_provider = True
            
        except ImportError as e:
            logger.warning(f"kis_auth 패키지 없음. Mock으로 폴백: {e}")
            self._init_mock_provider()
            self._has_real_provider = False
        except Exception as e:
            logger.error(f"실제 KIS provider 초기화 실패: {e}")
            raise
    
    def _init_mock_provider(self):
        """Mock provider 초기화"""
        from .auth_mock import KISTokenProvider, KISAccountProvider
        
        config_path = self.config_loader.config_root
        env = "real" if self.mode == "real" else "devlp"
        
        self.token_provider = KISTokenProvider(config_path, env)
        self.account_provider = KISAccountProvider(config_path, env)
        
        logger.info(f"KIS Mock provider 초기화: env={env}")
        self._has_real_provider = False
    
    async def get_token(self) -> str:
        """인증 토큰 가져오기"""
        return self.token_provider.get_token()
    
    async def validate_token(self) -> bool:
        """토큰 검증"""
        return True
    
    def get_default_account(self) -> Optional[str]:
        """기본 계좌 번호 가져오기"""
        # 설정 파일 우선, 없으면 provider에서 가져오기
        account = self.config.get("default_account")
        if account:
            return account
        return self.account_provider.get_default_account()
    
    def get_config_root(self) -> str:
        """설정 디렉토리 경로"""
        return self.config_loader.config_root
    
    def is_real_mode(self) -> bool:
        """실제 모드인지 확인"""
        return self.mode == "real" and self._has_real_provider
    
    def get_accounts(self) -> List[KISAccount]:
        """계좌 목록 가져오기"""
        return self.config_loader.get_accounts()


class KisAuth(KISAuth):
    """Alias for compatibility"""
    pass