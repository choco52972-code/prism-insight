"""
공통 타입 정의
"""

from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime


class OrderType(str, Enum):
    """주문 유형"""
    LIMIT = "limit"      # 지정가
    MARKET = "market"    # 시장가
    STOP = "stop"        # 스톱


class OrderSide(str, Enum):
    """주문 방향"""
    BUY = "buy"          # 매수
    SELL = "sell"        # 매도


class MarketType(str, Enum):
    """시장 유형"""
    KOSPI = "kospi"      # 코스피
    KOSDAQ = "kosdaq"    # 코스닥
    KONEX = "konex"      # 코넥스
    ETF = "etf"          # ETF
    ETN = "etn"          # ETN


class OrderStatus(str, Enum):
    """주문 상태"""
    PENDING = "pending"      # 대기
    PLACED = "placed"        # 접수
    PARTIAL_FILLED = "partial_filled"  # 부분체결
    FILLED = "filled"        # 체결
    CANCELLED = "cancelled"  # 취소
    REJECTED = "rejected"    # 거부


class BrokerType(str, Enum):
    """브로커 유형"""
    KIS = "kis"              # 한국투자증권
    KIWOOM = "kiwoom"        # 키움증권
    DAISHIN = "daishin"      # 대신증권
    HANA = "hana"            # 하나증권
    MIRAE = "mirae"          # 미래에셋증권
    MOCK = "mock"            # 모의투자 (테스트용)


@dataclass
class BrokerConfig:
    """브로커 설정"""
    broker_type: BrokerType
    account_no: Optional[str] = None
    app_key: Optional[str] = None
    app_secret: Optional[str] = None
    is_simulation: bool = False  # 모의투자 여부
    rate_limit_per_second: int = 5  # 초당 요청 제한
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BrokerConfig':
        """딕셔너리에서 BrokerConfig 생성"""
        return cls(
            broker_type=BrokerType(data.get("broker_type", "kis")),
            account_no=data.get("account_no"),
            app_key=data.get("app_key"),
            app_secret=data.get("app_secret"),
            is_simulation=data.get("is_simulation", False),
            rate_limit_per_second=data.get("rate_limit_per_second", 5)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "broker_type": self.broker_type.value,
            "account_no": self.account_no,
            "app_key": self.app_key,
            "app_secret": self.app_secret,
            "is_simulation": self.is_simulation,
            "rate_limit_per_second": self.rate_limit_per_second
        }


@dataclass
class TradingResult:
    """거래 결과"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    order_id: Optional[str] = None
    timestamp: datetime = datetime.now()
    
    @classmethod
    def success(cls, data: Any = None, order_id: Optional[str] = None) -> 'TradingResult':
        """성공 결과 생성"""
        return cls(success=True, data=data, order_id=order_id)
    
    @classmethod
    def error(cls, error_msg: str) -> 'TradingResult':
        """에러 결과 생성"""
        return cls(success=False, error=error_msg)