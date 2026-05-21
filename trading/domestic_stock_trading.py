"""
Compatibility shim — re-exports from kis broker package.
All callers using `from trading.domestic_stock_trading import ...` continue to work unchanged.
"""
from trading.brokers.kis import (
    DomesticStockTrading,
    MultiAccountDomesticStockTrading,
    AsyncTradingContext,
    MultiAccountTradingContext,
)
import kis_auth as ka

__all__ = [
    "DomesticStockTrading",
    "MultiAccountDomesticStockTrading",
    "AsyncTradingContext",
    "MultiAccountTradingContext",
    "ka",
]
