"""
Prism Insight 설정 관리자
KIS와 Kiwoom 브로커를 설정 기반으로 관리하는 통합 매니저
"""

import os
import yaml
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from enum import Enum
import inspect

from .common import BrokerType, BrokerConfig
from .factory import BrokerFactory

logger = logging.getLogger(__name__)


class BrokerMode(Enum):
    """브로커 모드"""
    MOCK = "mock"
    REAL = "real"
    TEST = "test"


class BrokerConfigManager:
    """브로커 설정 관리자 클래스"""
    
    def __init__(self, config_root: Optional[str] = None):
        """
        Args:
            config_root: 설정 디렉토리 경로 (None이면 기본 경로 사용)
        """
        self.config_root = config_root or self._get_default_config_root()
        self._load_broker_configs()
        self.factory = BrokerFactory()
        logger.info(f"설정 관리자 초기화: {self.config_root}")
    
    def _get_default_config_root(self) -> str:
        """기본 설정 디렉토리 경로"""
        current_dir = Path(__file__).parent
        config_dir = current_dir / "config" / "brokers"
        if not config_dir.exists():
            config_dir.mkdir(parents=True, exist_ok=True)
        return str(config_dir)
    
    def _load_broker_configs(self):
        """브로커 설정 파일들 로드"""
        self.broker_configs = {}
        
        # KIS 설정
        kis_config_path = Path(self.config_root) / "kis_config.yaml"
        if kis_config_path.exists():
            self.broker_configs[BrokerType.KIS] = self._load_yaml_config(kis_config_path)
            logger.info(f"KIS 설정 로드: {kis_config_path}")
        else:
            self.broker_configs[BrokerType.KIS] = self._get_default_kis_config()
            self._save_config(kis_config_path, self.broker_configs[BrokerType.KIS])
            logger.info(f"KIS 기본 설정 생성: {kis_config_path}")
        
        # Kiwoom 설정
        kiwoom_config_path = Path(self.config_root) / "kiwoom_config.yaml"
        if kiwoom_config_path.exists():
            self.broker_configs[BrokerType.KIWOOM] = self._load_yaml_config(kiwoom_config_path)
            logger.info(f"Kiwoom 설정 로드: {kiwoom_config_path}")
        else:
            self.broker_configs[BrokerType.KIWOOM] = self._get_default_kiwoom_config()
            self._save_config(kiwoom_config_path, self.broker_configs[BrokerType.KIWOOM])
            logger.info(f"Kiwoom 기본 설정 생성: {kiwoom_config_path}")
    
    def _load_yaml_config(self, path: Path) -> Dict[str, Any]:
        """YAML 설정 파일 로드"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"설정 파일 로드 실패 {path}: {e}")
            return {}
    
    def _save_config(self, path: Path, config: Dict[str, Any]):
        """설정 파일 저장"""
        try:
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            logger.debug(f"설정 파일 저장: {path}")
        except Exception as e:
            logger.error(f"설정 파일 저장 실패 {path}: {e}")
    
    def _get_default_kis_config(self) -> Dict[str, Any]:
        """기본 KIS 설정"""
        return {
            "mode": "mock",  # "mock", "real"
            "api_key": "",
            "secret_key": "",
            "app_name": "Prism Insight KIS",
            "default_account": "1234567890",
            "accounts": [
                {
                    "account_no": "1234567890",
                    "account_type": "일반",
                    "nickname": "주거래 계좌",
                    "main": True,
                    "broker": "kis"
                }
            ],
            "api_config": {
                "base_url": "https://openapi.koreainvestment.com:9443",
                "oauth_url": "https://openapivts.koreainvestment.com:29443",
                "timeout": 30,
                "max_retries": 3
            },
            "trading": {
                "fee_rate": 0.00015,
                "tax_rate": 0.0003,
                "min_order_amount": 10000,
                "max_order_amount": 1000000000
            },
            "mock_config": {
                "initial_balance": 100000000,
                "stock_count": 50,
                "price_variation_pct": 3.0,
                "trade_success_rate": 0.95
            },
            "description": "KIS 브로커 설정 (한국투자증권)"
        }
    
    def _get_default_kiwoom_config(self) -> Dict[str, Any]:
        """기본 Kiwoom 설정"""
        return {
            "mode": "mock",  # "mock", "real"
            "api_key": "",
            "secret_key": "",
            "app_name": "Prism Insight Kiwoom",
            "default_account": "81203640",
            "accounts": [
                {
                    "account_no": "81203640",
                    "account_type": "일반",
                    "nickname": "모의투자 계좌",
                    "main": True,
                    "broker": "kiwoom",
                    "trade_type": "paper"  # "paper" (모의), "real" (실전)
                }
            ],
            "api_config": {
                "base_url": "",  # Kiwoom API URL
                "timeout": 30,
                "max_retries": 3,
                "rate_limit_per_second": 5
            },
            "trading": {
                "fee_rate": 0.00015,
                "tax_rate": 0.0003,
                "min_order_amount": 10000,
                "max_order_amount": 1000000000
            },
            "mock_config": {
                "initial_balance": 100000000,
                "stock_count": 30,
                "price_variation_pct": 2.5,
                "trade_success_rate": 0.97
            },
            "description": "Kiwoom 브로커 설정 (키움증권)"
        }
    
    def get_broker_config(self, broker_type: BrokerType) -> Dict[str, Any]:
        """특정 브로커 설정 가져오기"""
        return self.broker_configs.get(broker_type, {}).copy()
    
    def update_broker_config(self, broker_type: BrokerType, updates: Dict[str, Any]):
        """브로커 설정 업데이트"""
        if broker_type in self.broker_configs:
            # 기존 설정과 병합
            current = self.broker_configs[broker_type]
            
            # 깊은 병합 함수
            def deep_merge(source, updates):
                for key, value in updates.items():
                    if key in source and isinstance(source[key], dict) and isinstance(value, dict):
                        deep_merge(source[key], value)
                    else:
                        source[key] = value
            
            deep_merge(current, updates)
            
            # 파일 저장
            config_name = "kis_config.yaml" if broker_type == BrokerType.KIS else "kiwoom_config.yaml"
            config_path = Path(self.config_root) / config_name
            self._save_config(config_path, current)
            
            logger.info(f"브로커 설정 업데이트: {broker_type}")
        else:
            logger.warning(f"알 수 없는 브로커 타입: {broker_type}")
    
    def set_broker_mode(self, broker_type: BrokerType, mode: str):
        """브로커 모드 설정 (mock/real)"""
        self.update_broker_config(broker_type, {"mode": mode})
    
    def set_api_credentials(self, broker_type: BrokerType, api_key: str, secret_key: str):
        """API 자격증명 설정"""
        self.update_broker_config(broker_type, {
            "api_key": api_key,
            "secret_key": secret_key
        })
    
    def create_broker_instances(self, broker_type: BrokerType) -> Tuple[Any, Any]:
        """
        설정 기반으로 브로커 인스턴스 생성
        
        Returns:
            (auth_instance, trading_instance)
        """
        config_data = self.get_broker_config(broker_type)
        mode = config_data.get("mode", "mock")
        default_account = config_data.get("default_account", "")
        accounts = config_data.get("accounts", [])
        
        # BrokerConfig 생성
        broker_config = BrokerConfig(
            broker_type=broker_type,
            trading_mode=mode,
            config={
                "mode": mode,
                "config_root": str(Path(self.config_root).parent.parent),  # broker config 디렉토리 부모
                "default_account": default_account,
                "accounts": accounts,
                **config_data  # 나머지 설정 모두 포함
            }
        )
        
        # 팩토리를 통해 브로커 생성
        return self.factory.create_broker(broker_type, broker_config)
    
    def list_available_brokers(self) -> List[Dict[str, Any]]:
        """사용 가능한 브로커 목록"""
        available = self.factory.get_available_brokers()
        
        result = []
        for broker_type, auth_class in available.items():
            config = self.get_broker_config(broker_type)
            result.append({
                "type": broker_type,
                "name": broker_type.value.upper(),
                "mode": config.get("mode", "mock"),
                "auth_class": auth_class.__name__,
                "description": config.get("description", ""),
                "has_api_key": bool(config.get("api_key")),
                "accounts": len(config.get("accounts", [])),
                "enabled": True
            })
        
        return result
    
    def switch_broker(self, from_broker: BrokerType, to_broker: BrokerType) -> Dict[str, Any]:
        """
        브로커 전환 (설정 유지)
        
        Args:
            from_broker: 현재 브로커
            to_broker: 전환할 브로커
            
        Returns:
            전환 결과 정보
        """
        from_config = self.get_broker_config(from_broker)
        to_config = self.get_broker_config(to_broker)
        
        # 계좌 정보 전환 (기본 계좌 설정만)
        if from_config.get("accounts") and not to_config.get("accounts"):
            logger.info(f"계좌 정보 {from_broker} → {to_broker} 복사")
            self.update_broker_config(to_broker, {"accounts": from_config["accounts"]})
        
        return {
            "from": str(from_broker),
            "to": str(to_broker),
            "mode_changed": from_config.get("mode") != to_config.get("mode"),
            "message": f"브로커 전환: {from_broker} → {to_broker}"
        }


def broker_quick_start(broker_name: str = "kiwoom", mode: str = "mock") -> Tuple[Any, Any]:
    """
    빠른 시작 함수
    
    Args:
        broker_name: "kis" 또는 "kiwoom"
        mode: "mock" 또는 "real"
    
    Returns:
        (auth_instance, trading_instance)
    """
    # 문자열을 BrokerType으로 변환
    broker_name_lower = broker_name.lower()
    if broker_name_lower in ("kis", "한투", "koreainvestment"):
        broker_type = BrokerType.KIS
    elif broker_name_lower in ("kiwoom", "키움"):
        broker_type = BrokerType.KIWOOM
    else:
        raise ValueError(f"알 수 없는 브로커: {broker_name}")
    
    # 설정 관리자 생성
    manager = BrokerConfigManager()
    
    # 모드 설정 업데이트 (필요시)
    current_config = manager.get_broker_config(broker_type)
    if current_config.get("mode") != mode:
        manager.set_broker_mode(broker_type, mode)
    
    # 브로커 인스턴스 생성
    return manager.create_broker_instances(broker_type)


def discover_broker_configs() -> Dict[str, Path]:
    """설정 파일 검색"""
    configs = {}
    
    # KIS config 파일들
    kis_configs = [
        Path("/home/leedw/projects/kiwoom-trading-system/config/.env"),  # 기존 Kiwoom 시스템
        Path("~/.openclaw/credentials/kiwoom-api-key.json").expanduser(),  # OpenClaw 자격증명
        Path("/home/leedw/projects/prism-insight/trading/brokers/kiwoom/config/kiwoom_config.yaml"),  # Prism Insight
    ]
    
    for path in kis_configs:
        if path.exists():
            configs[str(path)] = path
    
    return configs


# Singleton 인스턴스
_config_manager: Optional[BrokerConfigManager] = None

def get_config_manager() -> BrokerConfigManager:
    """설정 관리자 싱글톤 인스턴스"""
    global _config_manager
    if _config_manager is None:
        _config_manager = BrokerConfigManager()
    return _config_manager