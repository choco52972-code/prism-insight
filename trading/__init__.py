"""
Prism Insight Trading Module
다중 브로커 지원 거래 시스템
"""

from .common import (
    BaseAuth,
    BaseTrading,
    Order, Balance, Position, MarketPrice,
    OrderType, OrderSide, MarketType, OrderStatus, BrokerType,
    BrokerConfig, TradingResult
)

# KIS 브로커 임포트 (Mock 버전)
from .brokers.kis import KisAuth, KisTrading, MultiAccountKisTrading

# Kiwoom 브로커 임포트
from .brokers.kiwoom import KiwoomAuth, KiwoomTrading

# 팩토리 임포트
from .factory import (
    BrokerFactory,
    get_broker_factory,
    create_broker,
    create_broker_from_string
)

# Legacy: `from trading import kis_auth as ka`
from .brokers.kis import kis_auth  # noqa: F401

# 설정 관리자 (선택적)
try:
    from .config_manager import BrokerConfigManager, broker_quick_start, get_config_manager
except ImportError:
    # 설정 관리자가 없으면 빈 클래스 정의
    BrokerConfigManager = None
    broker_quick_start = None
    get_config_manager = None

__all__ = [
    # 추상 클래스
    "BaseAuth",
    "BaseTrading",
    
    # 데이터 클래스
    "Order",
    "Balance",
    "Position",
    "MarketPrice",
    
    # 열거형
    "OrderType",
    "OrderSide",
    "MarketType",
    "OrderStatus",
    "BrokerType",
    
    # 설정 및 결과
    "BrokerConfig",
    "TradingResult",
    
    # 브로커 클래스
    # KIS (Mock)
    "KisAuth",
    "KisTrading",
    "MultiAccountKisTrading",
    
    # Kiwoom
    "KiwoomAuth",
    "KiwoomTrading",
    
    # 팩토리
    "BrokerFactory",
    "get_broker_factory",
    "create_broker",
    "create_broker_from_string",
    
    # 설정 관리자 (선택적)
    "BrokerConfigManager",
    "broker_quick_start",
    "get_config_manager"
]