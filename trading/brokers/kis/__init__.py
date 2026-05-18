"""
KIS Broker for Prism Insight — real trading via kis_original delegation.
"""

import sys
import logging

logger = logging.getLogger(__name__)

# Register the real kis_auth in sys.modules BEFORE importing any kis_original code.
# kis_original/domestic_stock_trading.py does `import kis_auth as ka` at module level;
# if sys.modules['kis_auth'] is already set here, it gets the real implementation
# instead of whatever the old mock injected.
try:
    import trading.brokers.kis_original.kis_auth as _real_kis_auth
    sys.modules['kis_auth'] = _real_kis_auth
    logger.debug("kis_auth registered → trading.brokers.kis_original.kis_auth")
except Exception as _e:
    logger.warning(f"Could not register real kis_auth: {_e}")

from .auth import KISAuth, KisAuth
from .trading import (
    DomesticStockTrading as KisTrading,
    AsyncTradingContext,
    MultiAccountKisTrading,
)

try:
    from .portfolio import KisPortfolioReporter
except ImportError:
    class KisPortfolioReporter:  # type: ignore[no-redef]
        pass

__all__ = [
    "KISAuth",
    "KisAuth",
    "KisTrading",
    "MultiAccountKisTrading",
    "AsyncTradingContext",
    "KisPortfolioReporter",
]
