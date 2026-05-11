"""
KIS Broker Trading 클래스 (설정 기반 Mock/Real)
KIS 거래 기능을 제공하는 클래스
"""

import asyncio
import logging
import time
import yaml
from pathlib import Path
from typing import Optional, Dict, List, Any, Union
from dataclasses import dataclass

from trading.common.base_trading import BaseTrading, Order, Balance, Position, MarketPrice

logger = logging.getLogger(__name__)


@dataclass
class KISTradingConfig:
    """KIS 거래 설정"""
    fee_rate: float = 0.00015  # 0.015%
    tax_rate: float = 0.0003   # 0.03%
    min_order_amount: int = 10000
    max_order_amount: int = 1000000000
    price_variation_pct: float = 3.0  # 가격 변동률
    
    
class DomesticStockTrading(BaseTrading):
    """KIS 국내주식 거래 클래스 (설정 기반)"""
    
    def __init__(self, auth):
        super().__init__()
        self.auth = auth
        self.mode = auth.mode if hasattr(auth, 'mode') else "mock"
        
        # 설정 로드
        self._config_cache = {}
        self._load_config()
        
        # Mock 거래 데이터
        self._mock_balance = Balance(
            total_balance=auth.config.get("mock_config", {}).get("initial_balance", 100000000),
            available_balance=auth.config.get("mock_config", {}).get("initial_balance", 100000000) * 0.98,
            deposit=auth.config.get("mock_config", {}).get("initial_balance", 100000000),
            evaluation_amount=auth.config.get("mock_config", {}).get("initial_balance", 100000000)
        )
        
        self._mock_positions = []
        self._mock_orders = {}
        self._order_counter = 1
        
        logger.info(f"KIS Trading 초기화: mode={self.mode}")
    
    def _load_config(self):
        """거래 설정 로드"""
        try:
            config = self.auth.config
            
            # 거래 설정
            trading_config = config.get("trading", {})
            self.trading_config = KISTradingConfig(
                fee_rate=trading_config.get("fee_rate", 0.00015),
                tax_rate=trading_config.get("tax_rate", 0.0003),
                min_order_amount=trading_config.get("min_order_amount", 10000),
                max_order_amount=trading_config.get("max_order_amount", 1000000000),
                price_variation_pct=trading_config.get("price_variation_pct", 3.0)
            )
            
            # Mock 설정
            mock_config = config.get("mock_config", {})
            self._initial_balance = mock_config.get("initial_balance", 100000000)
            self._stock_count = mock_config.get("stock_count", 50)
            self._trade_success_rate = mock_config.get("trade_success_rate", 0.95)
            
        except Exception as e:
            logger.warning(f"거래 설정 로드 실패, 기본값 사용: {e}")
            self.trading_config = KISTradingConfig()
            self._initial_balance = 100000000
            self._stock_count = 50
            self._trade_success_rate = 0.95
    
    def _generate_mock_position(self, idx: int) -> Position:
        """Mock 보유 포지션 생성"""
        symbols = ["005930", "000660", "035420", "005380", "051910",
                   "006400", "028260", "012330", "086790", "032640"]
        
        symbol = symbols[idx % len(symbols)]
        quantity = (idx + 1) * 10
        avg_price = [70000, 80000, 120000, 200000, 50000][idx % 5]
        current_price = avg_price * (1 + (self.trading_config.price_variation_pct / 100) * (idx % 3 - 1))
        
        return Position(
            symbol=symbol,
            quantity=quantity,
            average_price=avg_price,
            current_price=current_price,
            evaluation_amount=quantity * current_price,
            profit_loss=quantity * (current_price - avg_price),
            profit_loss_rate=((current_price - avg_price) / avg_price) * 100 if avg_price else 0
        )
    
    async def _ensure_client(self):
        """거래 클라이언트 준비"""
        if self.mode == "real" and self.auth.is_real_mode():
            # 실제 KIS 모드
            # 여기에 실제 KIS API 연결 코드
            logger.debug("실제 KIS 모드 (현재 Mock으로 동작)")
        # Mock 모드는 별도 처리가 필요 없음
    
    async def place_order(self, symbol: str, order_type: str, side: str, quantity: int,
                         price: Optional[float] = None, **kwargs) -> Order:
        """주문 실행"""
        await self._ensure_client()
        
        logger.info(f"place_order: {symbol} {side.upper()} {order_type} {quantity}@{price}")
        
        if self.mode == "mock":
            # Mock 주문 처리
            order_id = f"KIS_{self._order_counter:06d}"
            self._order_counter += 1
            
            # 실제 거래 로직 대신 Mock
            if self._trade_success_rate >= 1.0 or (hash(symbol + side) % 100) / 100.0 < self._trade_success_rate:
                status = "filled"
                filled_price = price or self._get_mock_price(symbol)
                
                # 잔고 업데이트 (간단한 Mock)
                order_value = filled_price * quantity
                self._mock_balance.total_balance -= order_value * 0.00015  # 수수료
                self._mock_balance.available_balance = self._mock_balance.total_balance * 0.98
                
                logger.info(f"Mock 주문 성공: {order_id}, 가격: {filled_price}")
            else:
                status = "rejected"
                filled_price = None
                logger.info(f"Mock 주문 거부: {order_id}")
            
            order = Order(
                symbol=symbol,
                order_type=order_type,
                side=side,
                quantity=quantity,
                price=price,
                order_id=order_id,
                status=status,
                account_no=kwargs.get("account_no") or self.auth.get_default_account()
            )
            
            self._mock_orders[order_id] = order
            return order
        
        else:
            # Mock으로 처리 (실제 구현은 추후)
            logger.warning("실제 KIS 모드는 현재 Mock으로 동작")
            return await self.place_order(symbol, order_type, side, quantity, price, **kwargs)
    
    async def cancel_order(self, order_id: str, **kwargs) -> bool:
        """주문 취소"""
        await self._ensure_client()
        
        logger.info(f"cancel_order: {order_id}")
        
        if order_id in self._mock_orders:
            order = self._mock_orders[order_id]
            if order.status in ["pending", "partially_filled"]:
                order.status = "canceled"
                return True
        
        return False
    
    async def get_balance(self, account_no: Optional[str] = None) -> Balance:
        """계좌 잔고 조회"""
        await self._ensure_client()
        
        logger.info(f"get_balance: {account_no or '기본계좌'}")
        
        if self.mode == "mock":
            # Mock 잔고 반환
            account = account_no or self.auth.get_default_account()
            logger.debug(f"Mock 잔고 반환: {account}, {self._mock_balance}")
            return self._mock_balance
        else:
            # 실전 모드는 Mock으로 대체
            logger.warning("실제 KIS 모드는 현재 Mock으로 동작")
            return await self.get_balance(account_no)
    
    async def get_positions(self, account_no: Optional[str] = None) -> List[Position]:
        """보유 포지션 조회"""
        await self._ensure_client()
        
        logger.info(f"get_positions: {account_no or '기본계좌'}")
        
        if self.mode == "mock":
            # Mock 포지션 생성
            if not self._mock_positions:
                self._mock_positions = [
                    self._generate_mock_position(i) 
                    for i in range(min(self._stock_count, 10))
                ]
            return self._mock_positions
        else:
            # 실전 모드는 Mock으로 대체
            logger.warning("실제 KIS 모드는 현재 Mock으로 동작")
            return await self.get_positions(account_no)
    
    async def get_order_status(self, order_id: str, **kwargs) -> Optional[Order]:
        """주문 상태 조회"""
        await self._ensure_client()
        
        logger.info(f"get_order_status: {order_id}")
        
        return self._mock_orders.get(order_id)
    
    async def get_order_history(self, start_date: Optional[str] = None,
                               end_date: Optional[str] = None, **kwargs) -> List[Order]:
        """주문 히스토리 조회"""
        await self._ensure_client()
        
        logger.info(f"get_order_history: {start_date} ~ {end_date}")
        
        return list(self._mock_orders.values())
    
    async def close(self):
        """리소스 정리"""
        logger.info("KIS Trading 리소스 정리")
        self._mock_positions.clear()
        self._mock_orders.clear()
    
    def _get_mock_price(self, symbol: str) -> float:
        """Mock 가격 생성"""
        # 심볼에 따라 기본 가격 설정
        base_prices = {
            "005930": 70000,  # 삼성전자
            "000660": 80000,  # SK하이닉스  
            "035420": 120000, # NAVER
            "005380": 200000, # 현대차
            "051910": 50000,  # LG화학
            "006400": 45000,  # 삼성SDI
            "028260": 35000,  # 삼성물산
            "012330": 28000,  # 현대모비스
            "086790": 22000,  # 셀트리온
            "032640": 18000,  # LG유플러스
        }
        
        base_price = base_prices.get(symbol, 50000)
        variation = self.trading_config.price_variation_pct / 100
        return base_price * (1 + variation * (hash(symbol) % 10 - 5) / 10.0)


# Alias for compatibility
KisTrading = DomesticStockTrading