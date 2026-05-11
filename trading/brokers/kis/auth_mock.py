"""
KIS Auth Mock 모듈 - kis_auth 모듈 대체
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# KIS 에러 클래스들
class KISAuthError(Exception):
    pass

class TokenFileError(KISAuthError):
    pass

class CredentialMismatchError(KISAuthError):
    pass

class TokenRequestError(KISAuthError):
    pass

class SecurityError(Exception):
    pass

# 상수
REFRESH_TOKEN_EXPIRED = "REFRESH_TOKEN_EXPIRED"
ACCESS_TOKEN_EXPIRED = "ACCESS_TOKEN_EXPIRED"

# 토큰 제공자 클래스
class KISTokenProvider:
    """KIS 토큰 제공자 Mock"""
    
    def __init__(self, config_path: str = "", env: str = "devlp"):
        self.config_path = config_path
        self.env = env
        logger.debug(f"KISTokenProvider Mock 초기화: config={config_path}, env={env}")
        
    def get_token(self) -> str:
        """토큰 가져오기 (Mock)"""
        logger.debug("KISTokenProvider.get_token() 호출 (Mock)")
        return "MOCK_KIS_TOKEN_1234567890"
        
    def refresh_token(self) -> str:
        """토큰 갱신 (Mock)"""
        logger.debug("KISTokenProvider.refresh_token() 호출 (Mock)")
        return "MOCK_KIS_REFRESHED_TOKEN_1234567890"
        
    def get_token_info(self) -> Dict[str, Any]:
        """토큰 정보 가져오기 (Mock)"""
        return {
            "access_token": "MOCK_KIS_TOKEN",
            "token_type": "Bearer",
            "expires_in": 86400,
            "issued_at": "2026-05-11T04:43:00Z"
        }

# 계좌 제공자 클래스  
class KISAccountProvider:
    """KIS 계좌 제공자 Mock"""
    
    def __init__(self, config_path: str = "", env: str = "devlp"):
        self.config_path = config_path
        self.env = env
        logger.debug(f"KISAccountProvider Mock 초기화: config={config_path}, env={env}")
        
    def get_accounts(self) -> list:
        """계좌 목록 가져오기 (Mock)"""
        logger.debug("KISAccountProvider.get_accounts() 호출 (Mock)")
        return [
            {"account_no": "1234567890", "account_type": "일반", "main": True},
            {"account_no": "0987654321", "account_type": "예탁", "main": False}
        ]
        
    def get_default_account(self) -> Optional[str]:
        """기본 계좌 가져오기 (Mock)"""
        accounts = self.get_accounts()
        for acc in accounts:
            if acc.get("main"):
                return acc["account_no"]
        return accounts[0]["account_no"] if accounts else None

# KISTokenProvider와 KISAccountProvider는 그대로 유지
        
    async def get_token(self) -> str:
        """인증 토큰 가져오기"""
        return self.token_provider.get_token()
        
    async def validate_token(self) -> bool:
        """토큰 검증 (항상 true)"""
        return True
        
    def get_default_account(self) -> Optional[str]:
        """기본 계좌 번호 가져오기"""
        return self.account_provider.get_default_account()
        
    def get_config_root(self) -> str:
        """설정 디렉토리 경로"""
        config_path = self.get_config("config_path", "")
        if config_path:
            return config_path
            
        # 기본 경로 생성
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(current_dir, "config")

# kis_auth 모듈로 사용 가능하도록
__all__ = [
    "KISAuthError",
    "TokenFileError", 
    "CredentialMismatchError",
    "TokenRequestError",
    "SecurityError",
    "REFRESH_TOKEN_EXPIRED",
    "ACCESS_TOKEN_EXPIRED",
    "KISTokenProvider",
    "KISAccountProvider",
    "KISAuth"
]