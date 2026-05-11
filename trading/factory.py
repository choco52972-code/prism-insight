"""
Broker Factory for creating broker instances
Multiple broker support (KIS, Kiwoom)
"""

import importlib
import logging
from typing import Dict, Any, Optional, Tuple, Type, Union

from .common import (
    BrokerConfig,
    BrokerType,
    BaseAuth,
    BaseTrading
)

logger = logging.getLogger(__name__)


class Broker:
    """Broker instance container"""
    
    def __init__(self, auth_cls: Type[BaseAuth], trading_cls: Type[BaseTrading]):
        self.auth_cls = auth_cls
        self.trading_cls = trading_cls
    
    def create(self, config: BrokerConfig) -> Tuple[BaseAuth, BaseTrading]:
        """Create broker instances"""
        auth_instance = self.auth_cls(config.config or {})
        trading_instance = self.trading_cls(auth_instance)
        return auth_instance, trading_instance


class BrokerRegistry:
    """Registry for broker implementations"""
    
    def __init__(self):
        self._brokers: Dict[BrokerType, Broker] = {}
        self._initialize_registry()
    
    def _initialize_registry(self):
        """Initialize with default brokers"""
        # KIS broker (Mock)
        try:
            from .brokers.kis import KisAuth, KisTrading
            self.register(BrokerType.KIS, KisAuth, KisTrading)
            logger.info(f"KIS broker registered: {BrokerType.KIS}")
        except ImportError as e:
            logger.warning(f"Failed to register KIS broker: {e}")
        
        # Kiwoom broker
        try:
            from .brokers.kiwoom import KiwoomAuth, KiwoomTrading
            self.register(BrokerType.KIWOOM, KiwoomAuth, KiwoomTrading)
            logger.info(f"Kiwoom broker registered: {BrokerType.KIWOOM}")
        except ImportError as e:
            logger.warning(f"Failed to register Kiwoom broker: {e}")
    
    def register(self, broker_type: BrokerType, auth_cls: Type[BaseAuth], 
                 trading_cls: Type[BaseTrading]) -> None:
        """Register a broker implementation"""
        self._brokers[broker_type] = Broker(auth_cls, trading_cls)
        logger.debug(f"Registered broker: {broker_type} -> {auth_cls.__name__}/{trading_cls.__name__}")
    
    def get(self, broker_type: BrokerType) -> Optional[Broker]:
        """Get broker by type"""
        return self._brokers.get(broker_type)
    
    def list_available(self) -> Dict[BrokerType, Type[BaseAuth]]:
        """List available brokers"""
        return {bt: broker.auth_cls for bt, broker in self._brokers.items()}
    
    def has_broker(self, broker_type: BrokerType) -> bool:
        """Check if broker is registered"""
        return broker_type in self._brokers


class BrokerFactory:
    """Main facade for creating brokers"""
    
    def __init__(self):
        self.registry = BrokerRegistry()
        logger.debug("BrokerFactory initialized")
    
    def create_broker(self, broker_type: BrokerType, config: BrokerConfig) -> Tuple[BaseAuth, BaseTrading]:
        """
        Create broker instances.
        
        Args:
            broker_type: Type of broker (KIS or Kiwoom)
            config: Broker configuration
            
        Returns:
            Tuple of (auth_instance, trading_instance)
            
        Raises:
            ValueError: If broker type is not supported
        """
        logger.info(f"Creating broker: {broker_type}, config={config}")
        
        broker = self.registry.get(broker_type)
        if not broker:
            available = list(self.registry.list_available().keys())
            raise ValueError(
                f"Broker type '{broker_type}' not supported. "
                f"Available brokers: {available}"
            )
        
        return broker.create(config)
    
    def get_available_brokers(self) -> Dict[BrokerType, Type[BaseAuth]]:
        """Get dictionary of available brokers and their auth classes"""
        return self.registry.list_available()
    
    def is_broker_available(self, broker_type: BrokerType) -> bool:
        """Check if a broker type is available"""
        return self.registry.has_broker(broker_type)


# Singleton instance
_singleton_factory: Optional[BrokerFactory] = None


def get_broker_factory() -> BrokerFactory:
    """Get the singleton broker factory instance"""
    global _singleton_factory
    if _singleton_factory is None:
        _singleton_factory = BrokerFactory()
    return _singleton_factory


def create_broker(broker_type: BrokerType, config: BrokerConfig) -> Tuple[BaseAuth, BaseTrading]:
    """Convenience function to create a broker"""
    return get_broker_factory().create_broker(broker_type, config)


def create_broker_from_string(type_str: str, trading_mode: str = "mock", 
                              **config) -> Tuple[BaseAuth, BaseTrading]:
    """
    Create broker from string.
    
    Args:
        type_str: 'kis' or 'kiwoom' (case-insensitive)
        trading_mode: 'mock' or 'real'
        **config: Additional configuration
        
    Returns:
        Tuple of (auth_instance, trading_instance)
    """
    type_str_lower = type_str.lower()
    
    # Map string to BrokerType
    if type_str_lower in ('kis', '한투', 'koreainvestment', '한국투자'):
        broker_type = BrokerType.KIS
    elif type_str_lower in ('kiwoom', '키움', '키움증권'):
        broker_type = BrokerType.KIWOOM
    else:
        raise ValueError(f"Unknown broker type: {type_str}")
    
    # Set mode based on trading_mode
    config_data = config.copy()
    if 'mode' not in config_data:
        config_data['mode'] = trading_mode
    
    broker_config = BrokerConfig(
        broker_type=broker_type,
        trading_mode=trading_mode,
        config=config_data
    )
    
    return create_broker(broker_type, broker_config)