"""
KIS Broker Trading — wraps kis_original/domestic_stock_trading.py via composition.

Implements BaseTrading for the multi-broker framework while exposing the full
original async_buy_stock / async_sell_stock / get_portfolio API for callers
that use DomesticStockTrading directly through this package.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, List, Any

from trading.common.base_trading import (
    BaseTrading, Order, Balance, Position, MarketPrice,
)

logger = logging.getLogger(__name__)


def _load_orig():
    """Import the original classes lazily to avoid circular-import issues."""
    from trading.brokers.kis_original.domestic_stock_trading import (
        DomesticStockTrading as _Orig,
        MultiAccountDomesticStockTrading as _OrigMulti,
    )
    return _Orig, _OrigMulti


class DomesticStockTrading(BaseTrading):
    """
    KIS 국내주식 거래 클래스.

    kis_original.DomesticStockTrading을 내부적으로 보유(composition)하고:
    - BaseTrading 추상 메서드를 구현해 다중 브로커 프레임워크와 호환
    - 기존 async_buy_stock / async_sell_stock / get_portfolio API를 그대로 노출
      하여 기존 호출부가 코드 변경 없이 계속 동작
    """

    def __init__(
        self,
        auth=None,
        mode: str = None,
        buy_amount: int = None,
        auto_trading: bool = None,
        account_name: str = None,
        account_index: int = None,
        product_code: str = "01",
    ):
        if auth is None:
            from trading.brokers.kis.auth import KisAuth
            auth = KisAuth()
        super().__init__(auth)

        _Orig, _ = _load_orig()
        _mode = mode if mode is not None else _Orig.DEFAULT_MODE
        _auto = auto_trading if auto_trading is not None else _Orig.AUTO_TRADING

        self._orig = _Orig(
            mode=_mode,
            buy_amount=buy_amount,
            auto_trading=_auto,
            account_name=account_name,
            account_index=account_index,
            product_code=product_code,
        )
        self.mode = self._orig.mode
        self.account_name = self._orig.account_name
        self.account_key = self._orig.account_key

    # ── BaseTrading abstract methods ──────────────────────────────────────

    async def get_current_price(self, symbol: str) -> MarketPrice:
        result = self._orig.get_current_price(symbol)
        if result is None:
            raise RuntimeError(f"get_current_price failed for {symbol}")
        return MarketPrice(
            symbol=result.get("stock_code", symbol),
            current_price=float(result.get("current_price", 0)),
            open_price=0.0,
            high_price=0.0,
            low_price=0.0,
            volume=int(result.get("volume", 0)),
            change=0.0,
            change_rate=float(result.get("change_rate", 0)),
            timestamp=datetime.now(),
        )

    async def get_balance(self, account_no: Optional[str] = None) -> Balance:
        summary = self._orig.get_account_summary()
        if summary is None:
            return Balance(
                total_balance=0, available_balance=0, deposit=0,
                evaluation_amount=0, profit_loss=0, profit_loss_rate=0,
            )
        return Balance(
            total_balance=float(summary.get("total_eval_amount", 0)),
            available_balance=float(summary.get("available_amount", 0)),
            deposit=float(summary.get("deposit", 0)),
            evaluation_amount=float(summary.get("total_eval_amount", 0)),
            profit_loss=float(summary.get("total_profit_amount", 0)),
            profit_loss_rate=float(summary.get("total_profit_rate", 0)),
        )

    async def get_positions(self, account_no: Optional[str] = None) -> List[Position]:
        portfolio = self._orig.get_portfolio()
        if not portfolio:
            return []
        return [
            Position(
                symbol=item.get("stock_code", ""),
                quantity=int(item.get("quantity", 0)),
                average_price=float(item.get("avg_price", 0)),
                current_price=float(item.get("current_price", 0)),
                evaluation_amount=float(item.get("eval_amount", 0)),
                profit_loss=float(item.get("profit_amount", 0)),
                profit_loss_rate=float(item.get("profit_rate", 0)),
            )
            for item in portfolio
        ]

    async def place_order(self, order: Order) -> Dict[str, Any]:
        limit_price = int(order.price) if order.price else None
        if order.side == "buy":
            return await self._orig.async_buy_stock(order.symbol, limit_price=limit_price)
        return await self._orig.async_sell_stock(order.symbol, limit_price=limit_price)

    async def cancel_order(self, order_id: str, symbol: str,
                           account_no: Optional[str] = None) -> bool:
        # KIS 국내주식 API는 취소 주문을 별도 엔드포인트로 처리; 현재 미지원
        return False

    async def get_order_status(self, order_id: str, symbol: str,
                               account_no: Optional[str] = None) -> Dict[str, Any]:
        return {"order_id": order_id, "status": "unknown"}

    # ── Original API passthrough (backward compat) ────────────────────────

    async def async_buy_stock(self, stock_code: str, buy_amount: int = None,
                              timeout: float = 30.0,
                              limit_price: int = None) -> Dict[str, Any]:
        return await self._orig.async_buy_stock(
            stock_code, buy_amount=buy_amount, timeout=timeout, limit_price=limit_price,
        )

    async def async_sell_stock(self, stock_code: str, timeout: float = 30.0,
                               limit_price: int = None) -> Dict[str, Any]:
        return await self._orig.async_sell_stock(
            stock_code, timeout=timeout, limit_price=limit_price,
        )

    def get_portfolio(self) -> List[Dict[str, Any]]:
        return self._orig.get_portfolio()

    def get_account_summary(self) -> Optional[Dict[str, Any]]:
        return self._orig.get_account_summary()

    def calculate_buy_quantity(self, stock_code: str,
                               buy_amount: int = None) -> int:
        return self._orig.calculate_buy_quantity(stock_code, buy_amount=buy_amount)

    def get_holding_quantity(self, stock_code: str) -> int:
        return self._orig.get_holding_quantity(stock_code)


# Populate class-level constants from the original (needed by AsyncTradingContext)
try:
    _Orig, _ = _load_orig()
    DomesticStockTrading.DEFAULT_BUY_AMOUNT = _Orig.DEFAULT_BUY_AMOUNT
    DomesticStockTrading.AUTO_TRADING = _Orig.AUTO_TRADING
    DomesticStockTrading.DEFAULT_MODE = _Orig.DEFAULT_MODE
except Exception:
    DomesticStockTrading.DEFAULT_BUY_AMOUNT = 1_000_000
    DomesticStockTrading.AUTO_TRADING = False
    DomesticStockTrading.DEFAULT_MODE = "demo"


class AsyncTradingContext:
    """
    Async context manager — yields a DomesticStockTrading instance.
    Drop-in replacement for the original AsyncTradingContext.
    """

    AUTO_TRADING = DomesticStockTrading.AUTO_TRADING
    DEFAULT_MODE = DomesticStockTrading.DEFAULT_MODE

    def __init__(
        self,
        mode: str = None,
        buy_amount: int = None,
        auto_trading: bool = None,
        account_name: str = None,
        account_index: int = None,
        product_code: str = "01",
    ):
        self._kwargs = dict(
            mode=mode,
            buy_amount=buy_amount,
            auto_trading=auto_trading,
            account_name=account_name,
            account_index=account_index,
            product_code=product_code,
        )
        self._trader: Optional[DomesticStockTrading] = None

    async def __aenter__(self) -> DomesticStockTrading:
        self._trader = DomesticStockTrading(**self._kwargs)
        return self._trader

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass


class MultiAccountKisTrading:
    """Multi-account fanout trading — wraps MultiAccountDomesticStockTrading."""

    def __init__(
        self,
        mode: str = None,
        buy_amount: int = None,
        auto_trading: bool = None,
        product_code: str = "01",
    ):
        _Orig, _OrigMulti = _load_orig()
        _mode = mode if mode is not None else _Orig.DEFAULT_MODE
        self._orig = _OrigMulti(
            mode=_mode,
            buy_amount=buy_amount,
            auto_trading=auto_trading,
            product_code=product_code,
        )

    async def async_buy_stock(self, stock_code: str, buy_amount: int = None,
                              timeout: float = 30.0,
                              limit_price: int = None) -> Dict[str, Any]:
        return await self._orig.async_buy_stock(
            stock_code, buy_amount=buy_amount, timeout=timeout, limit_price=limit_price,
        )

    async def async_sell_stock(self, stock_code: str, timeout: float = 30.0,
                               limit_price: int = None) -> Dict[str, Any]:
        return await self._orig.async_sell_stock(
            stock_code, timeout=timeout, limit_price=limit_price,
        )

    def get_portfolio(self) -> List[Dict[str, Any]]:
        return self._orig.get_portfolio()

    def get_account_summary(self) -> Optional[Dict[str, Any]]:
        return self._orig.get_account_summary()

    def get_current_price(self, stock_code: str) -> Optional[Dict[str, Any]]:
        return self._orig.get_current_price(stock_code)


# Alias
KisTrading = DomesticStockTrading
