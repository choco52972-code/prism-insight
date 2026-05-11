#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prism Insight - KIS & Kiwoom 브로커 사용 예시
설정 기반으로 브로커 선택 및 사용
"""

import asyncio
import sys
import os
from pathlib import Path

# 프로젝트 경로 추가
prism_insight_path = Path(__file__).parent.parent
sys.path.insert(0, str(prism_insight_path))

import logging
logging.basicConfig(level=logging.INFO)


async def example_1_config_manager():
    """예시 1: 설정 관리자를 통한 브로커 관리"""
    print("=" * 60)
    print("예시 1: 설정 관리자를 통한 브로커 관리")
    print("=" * 60)
    
    from trading.config_manager import BrokerConfigManager, broker_quick_start
    
    # 1. 설정 관리자 생성
    manager = BrokerConfigManager()
    
    # 2. 사용 가능한 브로커 목록 확인
    print("\n🔍 사용 가능한 브로커:")
    brokers = manager.list_available_brokers()
    for broker in brokers:
        print(f"   • {broker['name']}: {broker['mode']} 모드, 계좌 {broker['accounts']}개")
    
    # 3. 설정 확인
    print("\n⚙️ 현재 설정:")
    for broker_type, config in manager.broker_configs.items():
        mode = config.get("mode", "N/A")
        accounts = len(config.get("accounts", []))
        print(f"   • {broker_type.value}: {mode} 모드, 계좌 {accounts}개")
    
    # 4. 빠른 시작 (Kiwoom 모의 모드)
    print("\n🚀 빠른 시작 (Kiwoom 모의 모드):")
    auth, trading = broker_quick_start("kiwoom", "mock")
    print(f"   - auth: {auth}")
    print(f"   - trading: {trading}")
    print(f"   - 모드: {auth.mode if hasattr(auth, 'mode') else 'N/A'}")
    
    # 5. 브로커 전환 예시
    print("\n🔄 브로커 전환 예시:")
    result = manager.switch_broker(broker.manager.kiwoom, broker.manager.kis)
    print(f"   - {result['message']}")
    
    return manager


async def example_2_broker_operations():
    """예시 2: 브로커 작업"""
    print("\n" + "=" * 60)
    print("예시 2: 브로커 작업 수행")
    print("=" * 60)
    
    from trading.config_manager import broker_quick_start
    
    # 1. Kiwoom 브로커 생성
    print("\n📊 Kiwoom 브로커로 작업:")
    try:
        kiwoom_auth, kiwoom_trading = broker_quick_start("kiwoom", "mock")
        
        # 잔고 조회
        balance = await kiwoom_trading.get_balance()
        print(f"   잔고: {balance.total_balance:,}원")
        print(f"   사용 가능: {balance.available_balance:,}원")
        
        # 포지션 조회
        positions = await kiwoom_trading.get_positions()
        print(f"   보유 종목: {len(positions)}개")
        if positions:
            print(f"   예시 종목: {positions[0].symbol} {positions[0].quantity}주")
        
        # 주문 예시 (모의)
        order = await kiwoom_trading.place_order(
            symbol="005930",
            order_type="limit",
            side="buy",
            quantity=10,
            price=70000
        )
        print(f"   모의 주문: {order.order_id} ({order.status})")
        
        # 리소스 정리
        await kiwoom_trading.close()
        print("   ✅ 리소스 정리 완료")
        
    except Exception as e:
        print(f"   ❌ Kiwoom 작업 실패: {e}")
    
    # 2. KIS 브로커 생성
    print("\n📊 KIS 브로커로 작업:")
    try:
        kis_auth, kis_trading = broker_quick_start("kis", "mock")
        
        # 잔고 조회
        balance = await kis_trading.get_balance()
        print(f"   잔고: {balance.total_balance:,}원")
        
        # 포지션 조회
        positions = await kis_trading.get_positions()
        print(f"   보유 종목: {len(positions)}개")
        
        # KIS는 Mock이므로 기본적인 작업만
        print("   ✅ KIS Mock 작업 완료")
        
        await kis_trading.close()
        
    except Exception as e:
        print(f"   ❌ KIS 작업 실패: {e}")


async def example_3_factory_pattern():
    """예시 3: 팩토리 패턴 직접 사용"""
    print("\n" + "=" * 60)
    print("예시 3: 팩토리 패턴 직접 사용")
    print("=" * 60)
    
    from trading import BrokerFactory, BrokerType, BrokerConfig
    
    # 1. 팩토리 생성
    factory = BrokerFactory()
    
    # 2. 사용 가능 브로커 확인
    print("\n🏭 팩토리 상태:")
    available = factory.get_available_brokers()
    for broker_type, auth_class in available.items():
        print(f"   • {broker_type.value}: {auth_class.__name__}")
    
    # 3. Kiwoom 브로커 생성 (팩토리 직접 사용)
    print("\n🔧 Kiwoom 브로커 팩토리 생성:")
    kiwoom_config = BrokerConfig(
        broker_type=BrokerType.KIWOOM,
        trading_mode="mock",
        config={
            "mode": "mock",
            "account_no": "81203640",
            "custom_setting": "value"
        }
    )
    
    try:
        kiwoom_auth, kiwoom_trading = factory.create_broker(BrokerType.KIWOOM, kiwoom_config)
        print(f"   - 생성 완료: {kiwoom_auth.__class__.__name__}, {kiwoom_trading.__class__.__name__}")
        
        # 간단한 작업
        token = await kiwoom_auth.get_token()
        print(f"   - 토큰: {token[:20]}..." if token else "   - 토큰: (모의 모드)")
        
        await kiwoom_trading.close()
        
    except Exception as e:
        print(f"   ❌ 생성 실패: {e}")
    
    # 4. KIS 브로커 생성
    print("\n🔧 KIS 브로커 팩토리 생성:")
    kis_config = BrokerConfig(
        broker_type=BrokerType.KIS,
        trading_mode="mock",
        config={"mode": "mock"}
    )
    
    try:
        kis_auth, kis_trading = factory.create_broker(BrokerType.KIS, kis_config)
        print(f"   - 생성 완료: {kis_auth.__class__.__name__}, {kis_trading.__class__.__name__}")
        await kis_trading.close()
    except Exception as e:
        print(f"   ❌ 생성 실패: {e}")


def example_4_configuration():
    """예시 4: 설정 변경 및 관리"""
    print("\n" + "=" * 60)
    print("예시 4: 설정 변경 및 관리")
    print("=" * 60)
    
    from trading.config_manager import BrokerConfigManager
    
    manager = BrokerConfigManager()
    
    # 1. 설정 확인
    print("\n📁 현재 설정 파일:")
    config_root = Path(manager.config_root)
    for file in config_root.glob("*.yaml"):
        print(f"   • {file.name}")
    
    # 2. 설정 업데이트 예시
    print("\n🔄 설정 업데이트 예시:")
    
    # Kiwoom 모드 변경 (mock → real)
    current_mode = manager.get_broker_config(manager.factory.KIWOOM).get("mode", "mock")
    print(f"   Kiwoom 현재 모드: {current_mode}")
    
    # API 키 설정 예시 (실제로는 안전하게 저장)
    print("\n🔑 API 키 설정 예시 (실제 앱):")
    print("   manager.set_api_credentials(BrokerType.KIWOOM, 'your_api_key', 'your_secret_key')")
    print("   manager.set_broker_mode(BrokerType.KIWOOM, 'real')")
    
    # 3. 설정 백업 예시
    print("\n💾 설정 백업:")
    import yaml
    backup_path = Path("/tmp/prism_insight_backup.yaml")
    backup_data = {
        "timestamp": "2026-05-11T04:50:00",
        "brokers": manager.broker_configs
    }
    
    with open(backup_path, 'w', encoding='utf-8') as f:
        yaml.dump(backup_data, f, default_flow_style=False)
    
    print(f"   백업 저장: {backup_path}")


async def example_5_real_world_usage():
    """예시 5: 실제 사용 시나리오"""
    print("\n" + "=" * 60)
    print("예시 5: 실제 사용 시나리오")
    print("=" * 60)
    
    print("\n📈 시나리오 1: 모의 투자 전략 테스트")
    print("""
    1. 설정 관리자로 Kiwoom 모의 모드 브로커 생성
    2. 백테스팅 엔진과 연결
    3. 모의 주문 실행 및 결과 분석
    4. 실전 모드로 전환 준비
    """)
    
    print("\n🏦 시나리오 2: 멀티 브로커 포트폴리오 관리")
    print("""
    1. KIS와 Kiwoom 브로커 모두 생성
    2. 각 브로커별 잔고 및 포지션 조회
    3. 통합 포트폴리오 리포트 생성
    4. 자동 리밸런싱 실행
    """)
    
    print("\n⚙️ 시나리오 3: 데모 앱 개발")
    print("""
    1. 설정 UI 제공 (KIS/Kiwoom 선택)
    2. 모드 선택 (모의/실전)
    3. API 키 입력 및 저장
    4. 테스트 연결 및 사용자 피드백
    """)


def create_quick_guide():
    """빠른 시작 가이드 출력"""
    print("\n" + "=" * 60)
    print("🚀 Prism Insight 브로커 사용 빠른 가이드")
    print("=" * 60)
    
    guide = """
📌 설정 파일 위치:
   • KIS 설정: trading/brokers/kis/config/kis_config.yaml
   • Kiwoom 설정: trading/brokers/kiwoom/config/kiwoom_config.yaml

📌 기본 사용법:

1. 빠른 시작 (가장 쉬움):
   from trading.config_manager import broker_quick_start
   auth, trading = broker_quick_start("kiwoom", "mock")

2. 설정 관리자 사용:
   from trading.config_manager import BrokerConfigManager
   manager = BrokerConfigManager()
   auth, trading = manager.create_broker_instances(BrokerType.KIWOOM)

3. 팩토리 직접 사용:
   from trading import BrokerFactory, BrokerType, BrokerConfig
   factory = BrokerFactory()
   config = BrokerConfig(broker_type=BrokerType.KIWOOM, trading_mode="mock")
   auth, trading = factory.create_broker(BrokerType.KIWOOM, config)

📌 모드 전환:
   - 모의(mock): 설정 파일에서 mode: "mock"
   - 실전(real): mode: "real" + API 키 설정

📌 API 키 설정:
   # 설정 관리자를 통해
   manager.set_api_credentials(BrokerType.KIWOOM, "api_key", "secret_key")
   manager.set_broker_mode(BrokerType.KIWOOM, "real")

📌 브로커 비교:
   • KIS: 한국투자증권, 전문투자자용
   • Kiwoom: 키움증권, 개인투자자 친화적
   • 둘 다 설정 파일 기반으로 동일하게 사용 가능
    """
    
    print(guide)


async def main():
    """메인 예시 실행"""
    print("🔧 Prism Insight - KIS & Kiwoom 브로커 사용 예시")
    print("설정을 통한 브로커 선택 및 관리\n")
    
    # 예시 실행
    manager = await example_1_config_manager()
    await example_2_broker_operations()
    await example_3_factory_pattern()
    example_4_configuration()
    await example_5_real_world_usage()
    create_quick_guide()
    
    print("\n" + "=" * 60)
    print("✅ KIS와 Kiwoom 브로커 설정 기반 사용 준비 완료!")
    print("=" * 60)
    print("\n이제 KIS와 Kiwoom을 설정 파일을 통해 쉽게 선택하고 사용할 수 있습니다.")


if __name__ == "__main__":
    # 비동기 예시 실행
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n\n예시 종료")
    finally:
        loop.close()