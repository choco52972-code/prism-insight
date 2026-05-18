"""
Compatibility shim — re-exports from kis_original until migration completes.
All callers using `from trading.domestic_stock_trading import ...` continue to work unchanged.
"""
from trading.brokers.kis_original.domestic_stock_trading import (
    DomesticStockTrading,
    MultiAccountDomesticStockTrading,
    AsyncTradingContext,
    MultiAccountTradingContext,
)

__all__ = [
    "DomesticStockTrading",
    "MultiAccountDomesticStockTrading",
    "AsyncTradingContext",
    "MultiAccountTradingContext",
]
