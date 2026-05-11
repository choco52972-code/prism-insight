"""
브로커 인증 추상 클래스
모든 증권사 브로커는 이 클래스를 상속받아 구현해야 합니다.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union
import asyncio
import logging

logger = logging.getLogger(__name__)


class BaseAuth(ABC):
    """
    증권사 인증을 위한 추상 베이스 클래스
    
    모든 브로커 인증 클래스는 다음 메서드를 구현해야 합니다.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Args:
            config: 브로커별 설정 딕셔너리
        """
        self.config = config or {}
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expiry: Optional[float] = None
        self._authenticated = False
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """
        인증 수행 (토큰 획득)
        
        Returns:
            bool: 인증 성공 여부
        """
        pass
    
    @abstractmethod
    async def refresh_token(self) -> bool:
        """
        토큰 갱신
        
        Returns:
            bool: 갱신 성공 여부
        """
        pass
    
    @abstractmethod
    def get_access_token(self) -> Optional[str]:
        """
        현재 액세스 토큰 반환
        
        Returns:
            Optional[str]: 액세스 토큰 또는 None
        """
        pass
    
    @abstractmethod
    def is_authenticated(self) -> bool:
        """
        인증 상태 확인
        
        Returns:
            bool: 인증된 상태인지 여부
        """
        pass
    
    @abstractmethod
    async def logout(self) -> bool:
        """
        로그아웃 처리
        
        Returns:
            bool: 로그아웃 성공 여부
        """
        pass
    
    # 선택적 메서드 (구현 권장)
    async def ensure_authenticated(self) -> bool:
        """
        인증 상태 확인 후 필요시 인증/갱신 수행
        
        Returns:
            bool: 인증된 상태인지 여부
        """
        if self.is_authenticated():
            return True
        
        try:
            # 토큰 갱신 시도
            if await self.refresh_token():
                return True
            
            # 갱신 실패 시 재인증
            return await self.authenticate()
        except Exception as e:
            logger.error(f"인증 확인 중 오류: {e}")
            return False
    
    def get_auth_headers(self) -> Dict[str, str]:
        """
        인증 헤더 반환 (기본 구현)
        
        Returns:
            Dict[str, str]: HTTP 요청 헤더
        """
        token = self.get_access_token()
        if not token:
            return {}
        
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        설정값 조회
        
        Args:
            key: 설정 키
            default: 기본값
            
        Returns:
            Any: 설정값
        """
        return self.config.get(key, default)
    
    def update_config(self, key: str, value: Any) -> None:
        """
        설정값 업데이트
        
        Args:
            key: 설정 키
            value: 설정값
        """
        self.config[key] = value
    
    def get_broker_name(self) -> str:
        """
        브로커 이름 반환
        
        Returns:
            str: 브로커 이름 (예: "kis", "kiwoom")
        """
        return self.get_config("broker_name", "unknown")