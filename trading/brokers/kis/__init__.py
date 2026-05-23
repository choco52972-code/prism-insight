"""
KIS Broker for Prism Insight.
"""

import sys
import logging

logger = logging.getLogger(__name__)

# Register the real kis_auth in sys.modules BEFORE importing _domestic.
# _domestic.py imports `kis_auth as ka` at module level; pre-registering here
# ensures it always gets the real implementation.
try:
    from . import kis_auth as _real_kis_auth
    sys.modules['kis_auth'] = _real_kis_auth
    logger.debug("kis_auth registered → trading.brokers.kis.kis_auth")
except Exception as _e:
    logger.warning(f"Could not register real kis_auth: {_e}")

from .auth import KISAuth, KisAuth
from .trading import (
    DomesticStockTrading,
    DomesticStockTrading as KisTrading,
    MultiAccountDomesticStockTrading,
    MultiAccountKisTrading,
    AsyncTradingContext,
    MultiAccountTradingContext,
)
try:
    from .portfolio import KisPortfolioReporter
except ImportError:
    class KisPortfolioReporter:  # type: ignore[no-redef]
        pass

__all__ = [
    "KISAuth",
    "KisAuth",
    "DomesticStockTrading",
    "KisTrading",
    "MultiAccountDomesticStockTrading",
    "MultiAccountKisTrading",
    "AsyncTradingContext",
    "MultiAccountTradingContext",
    "KisPortfolioReporter",
]
