"""
브로커 거래 추상 클래스
모든 증권사 브로커 거래 기능은 이 클래스를 상속받아 구현해야 합니다.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
from datetime import datetime
import logging
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class Order:
    """주문 정보"""
    symbol: str                    # 종목코드 (예: "005930")
    order_type: str               # 주문 유형: "limit", "market"
    side: str                     # 매수/매도: "buy", "sell"
    quantity: int                 # 수량
    price: Optional[float] = None # 가격 (시장가 주문일 경우 None)
    order_id: Optional[str] = None # 주문 ID
    status: Optional[str] = None  # 주문 상태
    account_no: Optional[str] = None # 계좌번호


@dataclass
class Balance:
    """계좌 잔고 정보"""
    total_balance: float          # 총 잔고
    available_balance: float      # 주문 가능 금액
    deposit: float                # 예수금
    evaluation_amount: float      # 평가금액
    profit_loss: float           # 평가손익
    profit_loss_rate: float      # 수익률 (%)


@dataclass
class Position:
    """보유 종목 정보"""
    symbol: str                   # 종목코드
    quantity: int                 # 보유 수량
    average_price: float          # 평균 단가
    current_price: float          # 현재가
    evaluation_amount: float      # 평가금액
    profit_loss: float           # 평가손익
    profit_loss_rate: float      # 수익률 (%)


@dataclass
class MarketPrice:
    """시세 정보"""
    symbol: str                   # 종목코드
    current_price: float          # 현재가
    open_price: float            # 시가
    high_price: float            # 고가
    low_price: float             # 저가
    volume: int                  # 거래량
    change: float                # 전일대비 변동
    change_rate: float           # 등락률 (%)
    timestamp: datetime          # 시세 시간


class BaseTrading(ABC):
    """
    증권사 거래를 위한 추상 베이스 클래스
    
    모든 브로커 거래 클래스는 다음 메서드를 구현해야 합니다.
    """
    
    def __init__(self, auth, config: Optional[Dict[str, Any]] = None):
        """
        Args:
            auth: BaseAuth 인스턴스
            config: 브로커별 설정 딕셔너리
        """
        self.auth = auth
        self.config = config or {}
        self._rate_limiter = None
        
    # 필수 메서드 (모든 브로커가 구현해야 함)
    
    @abstractmethod
    async def get_balance(self, account_no: Optional[str] = None) -> Balance:
        """
        계좌 잔고 조회
        
        Args:
            account_no: 계좌번호 (None일 경우 기본 계좌)
            
        Returns:
            Balance: 잔고 정보
        """
        pass
    
    @abstractmethod
    async def get_positions(self, account_no: Optional[str] = None) -> List[Position]:
        """
        보유 종목 조회
        
        Args:
            account_no: 계좌번호 (None일 경우 기본 계좌)
            
        Returns:
            List[Position]: 보유 종목 리스트
        """
        pass
    
    @abstractmethod
    async def get_current_price(self, symbol: str) -> MarketPrice:
        """
        현재가 조회
        
        Args:
            symbol: 종목코드
            
        Returns:
            MarketPrice: 시세 정보
        """
        pass
    
    @abstractmethod
    async def place_order(self, order: Order) -> Dict[str, Any]:
        """
        주문 전송
        
        Args:
            order: 주문 정보
            
        Returns:
            Dict[str, Any]: 주문 결과 (주문번호 포함)
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str, 
                          account_no: Optional[str] = None) -> bool:
        """
        주문 취소
        
        Args:
            order_id: 주문 ID
            symbol: 종목코드
            account_no: 계좌번호
            
        Returns:
            bool: 취소 성공 여부
        """
        pass
    
    @abstractmethod
    async def get_order_status(self, order_id: str, symbol: str,
                             account_no: Optional[str] = None) -> Dict[str, Any]:
        """
        주문 상태 조회
        
        Args:
            order_id: 주문 ID
            symbol: 종목코드
            account_no: 계좌번호
            
        Returns:
            Dict[str, Any]: 주문 상태 정보
        """
        pass
    
    # 선택적 메서드 (구현 권장)
    
    async def get_accounts(self) -> List[str]:
        """
        사용 가능한 계좌 목록 조회
        
        Returns:
            List[str]: 계좌번호 리스트
        """
        return []
    
    async def get_daily_prices(self, symbol: str, days: int = 30) -> List[MarketPrice]:
        """
        일별 시세 조회
        
        Args:
            symbol: 종목코드
            days: 조회 일수
            
        Returns:
            List[MarketPrice]: 일별 시세 리스트
        """
        # 기본 구현: 단일 조회 반환
        price = await self.get_current_price(symbol)
        return [price]
    
    async def batch_get_prices(self, symbols: List[str]) -> List[MarketPrice]:
        """
        여러 종목의 현재가 일괄 조회
        
        Args:
            symbols: 종목코드 리스트
            
        Returns:
            List[MarketPrice]: 시세 정보 리스트
        """
        prices = []
        for symbol in symbols:
            try:
                price = await self.get_current_price(symbol)
                prices.append(price)
            except Exception as e:
                logger.error(f"종목 {symbol} 가격 조회 실패: {e}")
                # 에러가 발생한 종목은 건너뛰기
                continue
        return prices
    
    async def validate_order(self, order: Order) -> Dict[str, Any]:
        """
        주문 유효성 검사
        
        Args:
            order: 주문 정보
            
        Returns:
            Dict[str, Any]: 검사 결과
        """
        validation = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # 기본 검사
        if order.quantity <= 0:
            validation["valid"] = False
            validation["errors"].append("수량은 0보다 커야 합니다.")
        
        if order.order_type == "limit" and (order.price is None or order.price <= 0):
            validation["valid"] = False
            validation["errors"].append("지정가 주문은 가격이 필요합니다.")
        
        if order.side not in ["buy", "sell"]:
            validation["valid"] = False
            validation["errors"].append("주문 방향은 'buy' 또는 'sell'이어야 합니다.")
        
        return validation
    
    def set_rate_limiter(self, rate_limiter):
        """
        Rate Limiter 설정
        
        Args:
            rate_limiter: RateLimiter 인스턴스
        """
        self._rate_limiter = rate_limiter
    
    async def _apply_rate_limit(self):
        """
        Rate Limiter 적용 (내부 메서드)
        """
        if self._rate_limiter:
            await self._rate_limiter.acquire()
    
    def get_broker_name(self) -> str:
        """
        브로커 이름 반환
        
        Returns:
            str: 브로커 이름
        """
        return self.auth.get_broker_name()
    
    async def health_check(self) -> Dict[str, Any]:
        """
        브로커 건강 상태 확인
        
        Returns:
            Dict[str, Any]: 상태 정보
        """
        try:
            # 기본 건강 체크: 인증 상태 확인
            authenticated = await self.auth.ensure_authenticated()
            
            return {
                "broker": self.get_broker_name(),
                "authenticated": authenticated,
                "timestamp": datetime.now().isoformat(),
                "status": "healthy" if authenticated else "unauthenticated"
            }
        except Exception as e:
            logger.error(f"브로커 건강 체크 실패: {e}")
            return {
                "broker": self.get_broker_name(),
                "authenticated": False,
                "error": str(e),
                "status": "error"
            }