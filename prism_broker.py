"""
Prism Insight 브로커 - KIS/Kiwoom 한 줄 전환
설정 파일 하나로 브로커 선택 가능
"""

import yaml
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class PrismBroker:
    """Prism Insight 브로커 매니저 (한 줄 전환)"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "config.yaml"
        self.config = self._load_config()
        self._broker = None
        self._auth = None
        
        logger.info(f"PrismBroker 초기화: {self.config['broker']} ({self.config['mode']} 모드)")
    
    def _load_config(self) -> Dict[str, Any]:
        """설정 파일 로드"""
        path = Path(self.config_path)
        if not path.exists():
            # 기본 설정 생성
            default_config = {
                "broker": "kiwoom",
                "mode": "mock",
                "account": {
                    "default_account": {
                        "kis": "1234567890",
                        "kiwoom": "81203640"
                    }
                }
            }
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)
            return default_config
        
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    
    def _create_broker(self) -> Tuple[Any, Any]:
        """설정에 따라 브로커 생성"""
        broker_type = self.config['broker']
        mode = self.config['mode']
        
        if broker_type == "kiwoom":
            return self._create_kiwoom_broker(mode)
        elif broker_type == "kis":
            return self._create_kis_broker(mode)
        else:
            raise ValueError(f"알 수 없는 브로커: {broker_type}")
    
    def _create_kiwoom_broker(self, mode: str) -> Tuple[Any, Any]:
        """Kiwoom 브로커 생성"""
        from trading.brokers.kiwoom import KiwoomAuth, KiwoomTrading
        
        # 계좌 설정
        account_no = self.config.get('account', {}).get('default_account', {}).get('kiwoom', '81203640')
        
        # 인증 설정
        auth_config = {
            "mode": mode,
            "account_no": account_no,
            "config_root": str(Path(__file__).parent / "trading" / "brokers" / "kiwoom" / "config")
        }
        
        auth = KiwoomAuth(auth_config)
        trading = KiwoomTrading(auth)
        
        return auth, trading
    
    def _create_kis_broker(self, mode: str) -> Tuple[Any, Any]:
        """KIS 브로커 생성"""
        from trading.brokers.kis import KisAuth, KisTrading
        
        # 계좌 설정
        account_no = self.config.get('account', {}).get('default_account', {}).get('kis', '1234567890')
        
        # 인증 설정
        auth_config = {
            "mode": mode,
            "account_no": account_no,
            "config_root": str(Path(__file__).parent / "trading" / "brokers" / "kis" / "config")
        }
        
        auth = KisAuth(auth_config)
        trading = KisTrading(auth)
        
        return auth, trading
    
    def switch_broker(self, broker_type: str, save: bool = True):
        """
        브로커 전환
        
        Args:
            broker_type: "kis" 또는 "kiwoom"
            save: 설정 파일에 저장할지 여부
        """
        if broker_type not in ["kis", "kiwoom"]:
            raise ValueError("broker_type은 'kis' 또는 'kiwoom'이어야 합니다")
        
        self.config['broker'] = broker_type
        
        if save:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
        
        # 새 브로커 생성
        self._auth, self._broker = self._create_broker()
        
        logger.info(f"브로커 전환 완료: {broker_type}")
    
    def get_broker(self):
        """현재 브로커 반환 (생성되지 않았다면 생성)"""
        if self._broker is None:
            self._auth, self._broker = self._create_broker()
        return self._auth, self._broker
    
    def get_current_config(self) -> Dict[str, Any]:
        """현재 설정 반환"""
        return self.config.copy()
    
    def update_config(self, updates: Dict[str, Any], save: bool = True):
        """설정 업데이트"""
        # 간단한 병합 (깊은 병합은 생략)
        for key, value in updates.items():
            if isinstance(value, dict) and key in self.config and isinstance(self.config[key], dict):
                self.config[key].update(value)
            else:
                self.config[key] = value
        
        if save:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
        
        # 브로커 재생성 필요
        self._auth, self._broker = self._create_broker()


# 전역 싱글톤
_prism_broker: Optional[PrismBroker] = None

def get_prism_broker(config_path: Optional[str] = None) -> PrismBroker:
    """PrismBroker 싱글톤 인스턴스"""
    global _prism_broker
    if _prism_broker is None:
        _prism_broker = PrismBroker(config_path)
    return _prism_broker


def create_broker(broker_type: str = None, mode: str = None) -> Tuple[Any, Any]:
    """
    브로커 생성 함수 (한 줄로 사용)
    
    Args:
        broker_type: None이면 설정 파일 값 사용, "kis" 또는 "kiwoom"
        mode: None이면 설정 파일 값 사용, "mock" 또는 "real"
    
    Returns:
        (auth_instance, trading_instance)
    """
    broker = get_prism_broker()
    
    # 브로커 타입 전환 (필요시)
    if broker_type and broker_type != broker.config['broker']:
        broker.switch_broker(broker_type)
    
    # 모드 업데이트 (필요시)
    if mode and mode != broker.config['mode']:
        broker.update_config({"mode": mode})
    
    return broker.get_broker()


async def example_usage():
    """사용 예시"""
    # ===== 방법 1: 기본 사용 (설정 파일대로) =====
    print("방법 1: 기본 사용")
    auth, trading = create_broker()
    print(f"현재 브로커: {type(auth).__name__}")
    
    # ===== 방법 2: Kiwoom으로 전환 =====
    print("\n방법 2: Kiwoom으로 전환")
    auth, trading = create_broker("kiwoom", "mock")
    balance = await trading.get_balance()
    print(f"Kiwoom 잔고: {balance.total_balance:,}원")
    
    # ===== 방법 3: KIS로 전환 =====
    print("\n방법 3: KIS로 전환")
    auth, trading = create_broker("kis", "mock")
    balance = await trading.get_balance()
    print(f"KIS 잔고: {balance.total_balance:,}원")
    
    # ===== 방법 4: 설정 관리자 직접 사용 =====
    print("\n방법 4: 설정 관리자 직접 사용")
    broker_mgr = get_prism_broker()
    print(f"현재 설정: {broker_mgr.get_current_config()['broker']}")
    
    # 브로커 전환
    broker_mgr.switch_broker("kiwoom")
    print(f"전환 후: {broker_mgr.get_current_config()['broker']}")


if __name__ == "__main__":
    # 비동기 예시 실행
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(example_usage())
    finally:
        loop.close()