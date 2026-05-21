"""
KIS Broker Trading — implements BaseTrading and exposes the full
async_buy_stock / async_sell_stock / get_portfolio API.
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
    from trading.brokers.kis._domestic import (
        DomesticStockTrading as _Orig,
        MultiAccountDomesticStockTrading as _OrigMulti,
    )
    return _Orig, _OrigMulti


class DomesticStockTrading(BaseTrading):
    """
    KIS 국내주식 거래 클래스.

    BaseTrading 추상 메서드를 구현해 다중 브로커 프레임워크와 호환하고,
    기존 async_buy_stock / async_sell_stock / get_portfolio API를 그대로 노출.
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
        self.buy_amount = self._orig.buy_amount
        self.account_name = self._orig.account_name
        self.account_key = self._orig.account_key

    def _request(self, api_url: str, tr_id: str, params: Dict[str, Any], **kwargs):
        """Serialized HTTP request with per-account lock."""
        if hasattr(self, '_orig'):
            return self._orig._request(api_url, tr_id, params, **kwargs)
        import kis_auth as _ka
        with _ka.get_trading_env_lock():
            self._activate_account()
            return _ka._url_fetch(api_url, tr_id, "", params, **kwargs)

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

    # ── Sync buy/sell passthrough ─────────────────────────────────────────

    def buy_market_price(self, stock_code: str, buy_amount: int = None) -> Dict[str, Any]:
        return self._orig.buy_market_price(stock_code, buy_amount=buy_amount)

    def buy_limit_price(self, stock_code: str, limit_price: int,
                        buy_amount: int = None) -> Dict[str, Any]:
        return self._orig.buy_limit_price(stock_code, limit_price, buy_amount=buy_amount)

    def smart_buy(self, stock_code: str, buy_amount: int = None,
                  limit_price: int = None) -> Dict[str, Any]:
        return self._orig.smart_buy(stock_code, buy_amount=buy_amount, limit_price=limit_price)

    def buy_closing_price(self, stock_code: str, buy_amount: int = None) -> Dict[str, Any]:
        return self._orig.buy_closing_price(stock_code, buy_amount=buy_amount)

    def buy_reserved_order(self, stock_code: str, buy_amount: int = None,
                           end_date: str = None,
                           limit_price: int = None) -> Dict[str, Any]:
        return self._orig.buy_reserved_order(
            stock_code, buy_amount=buy_amount, end_date=end_date, limit_price=limit_price,
        )

    def sell_all_market_price(self, stock_code: str) -> Dict[str, Any]:
        return self._orig.sell_all_market_price(stock_code)

    def smart_sell_all(self, stock_code: str,
                       limit_price: int = None) -> Dict[str, Any]:
        return self._orig.smart_sell_all(stock_code, limit_price=limit_price)

    def sell_all_closing_price(self, stock_code: str) -> Dict[str, Any]:
        return self._orig.sell_all_closing_price(stock_code)

    def sell_all_reserved_order(self, stock_code: str, end_date: str = None,
                                limit_price: int = None) -> Dict[str, Any]:
        return self._orig.sell_all_reserved_order(
            stock_code, end_date=end_date, limit_price=limit_price,
        )


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
            mode=mode if mode is not None else self.DEFAULT_MODE,
            buy_amount=buy_amount,
            auto_trading=auto_trading if auto_trading is not None else self.AUTO_TRADING,
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
    """Fan out trading orders to all configured domestic accounts."""

    def __init__(
        self,
        mode: str = None,
        buy_amount: int = None,
        auto_trading: bool = None,
        product_code: str = "01",
    ):
        import kis_auth as _ka
        _Orig, _ = _load_orig()
        _mode = mode if mode is not None else _Orig.DEFAULT_MODE
        _auto = auto_trading if auto_trading is not None else _Orig.AUTO_TRADING
        self.mode = _mode
        self.buy_amount = buy_amount
        self.auto_trading = _auto
        self.product_code = str(product_code)

        svr = "vps" if _mode == "demo" else "prod"
        self.account_configs = _ka.get_configured_accounts(
            svr=svr, product=self.product_code, market="kr",
        )
        self._traders: Dict[str, DomesticStockTrading] = {}
        self.primary_account = None
        try:
            self.primary_account = _ka.resolve_account(
                svr=svr, product=self.product_code, market="kr",
            )
        except ValueError:
            logger.warning("No domestic accounts configured for multi-account trading")

    def _get_trader(self, account: Dict[str, Any]) -> DomesticStockTrading:
        key = account["account_key"]
        if key not in self._traders:
            self._traders[key] = DomesticStockTrading(
                mode=self.mode,
                buy_amount=self.buy_amount,
                auto_trading=self.auto_trading,
                account_name=account["name"],
                product_code=account["product"],
            )
        return self._traders[key]

    def _get_primary_trader(self) -> DomesticStockTrading:
        if not self.primary_account:
            raise RuntimeError("No primary domestic account configured")
        return self._get_trader(self.primary_account)

    async def async_buy_stock(self, stock_code: str, buy_amount: int = None,
                              timeout: float = 30.0,
                              limit_price: int = None) -> Dict[str, Any]:
        if not self.account_configs:
            return self._aggregate_results(stock_code, [], action="buy")
        results = []
        for account in self.account_configs:
            trader = self._get_trader(account)
            result = await trader.async_buy_stock(
                stock_code, buy_amount=buy_amount, timeout=timeout, limit_price=limit_price,
            )
            result["account_name"] = account["name"]
            result["account_key"] = account["account_key"]
            results.append(result)
        return self._aggregate_results(stock_code, results, action="buy")

    async def async_sell_stock(self, stock_code: str, timeout: float = 30.0,
                               limit_price: int = None) -> Dict[str, Any]:
        if not self.account_configs:
            return self._aggregate_results(stock_code, [], action="sell")
        results = []
        for account in self.account_configs:
            trader = self._get_trader(account)
            result = await trader.async_sell_stock(
                stock_code, timeout=timeout, limit_price=limit_price,
            )
            result["account_name"] = account["name"]
            result["account_key"] = account["account_key"]
            results.append(result)
        return self._aggregate_results(stock_code, results, action="sell")

    def get_portfolio(self) -> List[Dict[str, Any]]:
        return self._get_primary_trader().get_portfolio()

    def get_account_summary(self) -> Optional[Dict[str, Any]]:
        return self._get_primary_trader().get_account_summary()

    def get_current_price(self, stock_code: str) -> Optional[Dict[str, Any]]:
        return self._get_primary_trader().get_current_price(stock_code)

    def calculate_buy_quantity(self, stock_code: str,
                               buy_amount: int = None) -> int:
        return self._get_primary_trader().calculate_buy_quantity(stock_code, buy_amount)

    def get_holding_quantity(self, stock_code: str) -> int:
        return self._get_primary_trader().get_holding_quantity(stock_code)

    def _aggregate_results(self, stock_code: str, results: List[Dict[str, Any]],
                           action: str) -> Dict[str, Any]:
        total = len(results)
        success_count = sum(1 for r in results if r.get("success"))
        successful = [r.get("account_name") for r in results if r.get("success")]
        failed = [r.get("account_name") for r in results if not r.get("success")]
        total_qty = sum(r.get("quantity", 0) for r in results)
        total_amt = sum(r.get("total_amount", r.get("estimated_amount", 0)) for r in results)
        messages = [f"{r.get('account_name')}: {r.get('message', '')}" for r in results]

        if total == 0:
            return {
                "success": False, "partial_success": False,
                "stock_code": stock_code, "quantity": 0,
                "total_amount": 0, "estimated_amount": 0, "order_no": None,
                "message": f"No domestic accounts configured for {action}",
                "account_results": [], "successful_accounts": [], "failed_accounts": [],
            }
        return {
            "success": success_count == total and total > 0,
            "partial_success": 0 < success_count < total,
            "stock_code": stock_code, "quantity": total_qty,
            "total_amount": total_amt, "estimated_amount": total_amt, "order_no": None,
            "message": f"{action} executed for {success_count}/{total} accounts | " + " ; ".join(messages),
            "account_results": results,
            "successful_accounts": successful,
            "failed_accounts": failed,
        }


# Alias — backward compat name used by the shim and tests
MultiAccountDomesticStockTrading = MultiAccountKisTrading


class MultiAccountTradingContext:
    """Async context manager for multi-account domestic trading."""

    def __init__(
        self,
        mode: str = None,
        buy_amount: int = None,
        auto_trading: bool = None,
        product_code: str = "01",
    ):
        self._kwargs = dict(
            mode=mode,
            buy_amount=buy_amount,
            auto_trading=auto_trading,
            product_code=product_code,
        )
        self._trader: Optional[MultiAccountKisTrading] = None

    async def __aenter__(self) -> MultiAccountKisTrading:
        self._trader = MultiAccountKisTrading(**self._kwargs)
        return self._trader

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            logger.error(f"MultiAccountTradingContext error: {exc_type.__name__}: {exc_val}")


# Alias
KisTrading = DomesticStockTrading
