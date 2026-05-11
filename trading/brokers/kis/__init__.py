"""
KIS Broker for Prism Insight
설정 기반 KIS broker (Mock/Real 선택 가능)
"""

import sys
import types
import logging

logger = logging.getLogger(__name__)

# kis_auth 모듈 Mock 생성 (auth_mock.py 사용)
try:
    # 먼저 auth_mock에서 provider 클래스들 임포트
    from .auth_mock import (
        KISAuthError,
        TokenFileError,
        CredentialMismatchError,
        TokenRequestError,
        SecurityError,
        REFRESH_TOKEN_EXPIRED,
        ACCESS_TOKEN_EXPIRED,
        KISTokenProvider,
        KISAccountProvider
    )
    
    # kis_auth 모듈 생성
    def _create_kis_auth_module():
        kis_auth_module = types.ModuleType('kis_auth')
        
        # 에러 클래스
        kis_auth_module.KISAuthError = KISAuthError
        kis_auth_module.TokenFileError = TokenFileError
        kis_auth_module.CredentialMismatchError = CredentialMismatchError
        kis_auth_module.TokenRequestError = TokenRequestError
        kis_auth_module.SecurityError = SecurityError
        
        # 상수
        kis_auth_module.REFRESH_TOKEN_EXPIRED = REFRESH_TOKEN_EXPIRED
        kis_auth_module.ACCESS_TOKEN_EXPIRED = ACCESS_TOKEN_EXPIRED
        
        # Provider 클래스
        kis_auth_module.KISTokenProvider = KISTokenProvider
        kis_auth_module.KISAccountProvider = KISAccountProvider
        
        return kis_auth_module
    
    kis_auth_module = _create_kis_auth_module()
    sys.modules['kis_auth'] = kis_auth_module
    
    # 서브모듈 생성
    sys.modules['kis_auth.types'] = types.ModuleType('kis_auth.types')
    sys.modules['kis_auth.auth'] = types.ModuleType('kis_auth.auth')
    
    logger.info("kis_auth Mock 모듈 생성 완료")
    
except Exception as e:
    logger.error(f"kis_auth Mock 모듈 생성 실패: {e}")

# 메인 KIS 클래스들 임포트
from .auth import KISAuth, KisAuth
from .trading import DomesticStockTrading as KisTrading

# MultiAccountKisTrading alias
MultiAccountKisTrading = KisTrading

# KisPortfolioReporter (필요시)
try:
    from .portfolio import KisPortfolioReporter
except ImportError:
    class KisPortfolioReporter:
        """KIS 포트폴리오 리포트 Mock"""
        pass

__all__ = [
    "KISAuth",
    "KisAuth",
    "KisTrading",
    "MultiAccountKisTrading",
    "KisPortfolioReporter"
]