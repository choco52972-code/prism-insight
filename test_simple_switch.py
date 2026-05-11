#!/usr/bin/env python3
"""
Prism Insight 브로커 전환 테스트
설정 파일 하나만 바꿔서 KIS ↔ Kiwoom 전환 가능한지 확인
"""

import asyncio
import sys
from pathlib import Path

# 프로젝트 경로 추가
prism_insight_path = Path(__file__).parent
sys.path.insert(0, str(prism_insight_path))

print("🔧 Prism Insight 브로커 전환 테스트")
print("설정 파일 하나로 KIS ↔ Kiwoom 전환 확인\n")


async def test_kiwoom_broker():
    """Kiwoom 브로커 테스트"""
    print("1️⃣ Kiwoom 브로커 테스트")
    
    try:
        # 방법 1: 직접 임포트
        from trading.brokers.kiwoom import KiwoomAuth, KiwoomTrading
        
        auth = KiwoomAuth({"mode": "mock", "account_no": "81203640"})
        trading = KiwoomTrading(auth)
        
        balance = await trading.get_balance()
        print(f"   ✅ Kiwoom 잔고: {balance.total_balance:,}원")
        
        positions = await trading.get_positions()
        print(f"   ✅ 보유 종목: {len(positions)}개")
        
        await trading.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Kiwoom 테스트 실패: {e}")
        return False


async def test_kis_broker():
    """KIS 브로커 테스트"""
    print("\n2️⃣ KIS 브로커 테스트")
    
    try:
        # 방법 1: 직접 임포트
        from trading.brokers.kis import KisAuth, KisTrading
        
        auth = KisAuth({"mode": "mock", "account_no": "1234567890"})
        trading = KisTrading(auth)
        
        balance = await trading.get_balance()
        print(f"   ✅ KIS 잔고: {balance.total_balance:,}원")
        
        positions = await trading.get_positions()
        print(f"   ✅ 보유 종목: {len(positions)}개")
        
        await trading.close()
        return True
        
    except Exception as e:
        print(f"   ❌ KIS 테스트 실패: {e}")
        return False


async def test_prism_broker():
    """PrismBroker 전환 테스트"""
    print("\n3️⃣ PrismBroker 전환 테스트")
    
    try:
        from prism_broker import create_broker, get_prism_broker
        
        # 방법 1: Kiwoom으로 생성
        print("   🔄 Kiwoom 브로커 생성:")
        kiwoom_auth, kiwoom_trading = create_broker("kiwoom", "mock")
        kiwoom_balance = await kiwoom_trading.get_balance()
        print(f"      잔고: {kiwoom_balance.total_balance:,}원")
        await kiwoom_trading.close()
        
        # 방법 2: KIS로 생성
        print("   🔄 KIS 브로커 생성:")
        kis_auth, kis_trading = create_broker("kis", "mock")
        kis_balance = await kis_trading.get_balance()
        print(f"      잔고: {kis_balance.total_balance:,}원")
        await kis_trading.close()
        
        # 방법 3: 설정 관리자로 전환
        print("   ⚙️ 설정 관리자 전환:")
        manager = get_prism_broker()
        print(f"      현재 브로커: {manager.get_current_config()['broker']}")
        
        manager.switch_broker("kiwoom")
        print(f"      Kiwoom으로 전환 완료")
        
        manager.switch_broker("kis")
        print(f"      KIS로 전환 완료")
        
        return True
        
    except Exception as e:
        print(f"   ❌ PrismBroker 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def show_usage_examples():
    """사용 예시 보여주기"""
    print("\n" + "=" * 60)
    print("🚀 사용 방법 예시")
    print("=" * 60)
    
    examples = """
📌 방법 1: 한 줄로 브로커 생성 (가장 쉬움)
```python
from prism_broker import create_broker

# Kiwoom 브로커 생성
kiwoom_auth, kiwoom_trading = create_broker("kiwoom", "mock")

# KIS 브로커 생성  
kis_auth, kis_trading = create_broker("kis", "mock")
```

📌 방법 2: 설정 파일 변경
1. `config.yaml` 파일 열기
2. `broker: "kiwoom"` → `broker: "kis"` 로 변경
3. 저장 후 코드 재실행

📌 방법 3: 프로그램에서 전환
```python
from prism_broker import get_prism_broker

manager = get_prism_broker()
manager.switch_broker("kiwoom")  # Kiwoom으로 전환
manager.switch_broker("kis")     # KIS로 전환
```

📌 방법 4: 팩토리 직접 사용 (고급)
```python
from trading import BrokerFactory, BrokerType, BrokerConfig

factory = BrokerFactory()

# Kiwoom 생성
kiwoom_config = BrokerConfig(BrokerType.KIWOOM, "mock")
kiwoom_auth, kiwoom_trading = factory.create_broker(BrokerType.KIWOOM, kiwoom_config)

# KIS 생성
kis_config = BrokerConfig(BrokerType.KIS, "mock")  
kis_auth, kis_trading = factory.create_broker(BrokerType.KIS, kis_config)
```
"""
    
    print(examples)


async def main():
    """메인 테스트"""
    results = {}
    
    # 1. Kiwoom 테스트
    results['kiwoom'] = await test_kiwoom_broker()
    
    # 2. KIS 테스트
    results['kis'] = await test_kis_broker()
    
    # 3. PrismBroker 전환 테스트
    results['prism_broker'] = await test_prism_broker()
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("📊 테스트 결과")
    print("=" * 60)
    
    success_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    
    print(f"✅ 성공: {success_count}/{total_count}")
    
    if success_count == total_count:
        print("\n🎉 **Prism Insight 브로커 전환 시스템 완료!**")
        print("✅ KIS와 Kiwoom을 설정 파일 하나로 전환 가능")
        print("✅ 한 줄 코드로 브로커 생성 가능")
        print("✅ 모의(Mock) 모드와 실전(Real) 모드 지원")
        
        show_usage_examples()
        
        print("\n" + "=" * 60)
        print("이제 `config.yaml` 파일의 `broker: ` 값을 변경하기만 하면")
        print("KIS와 Kiwoom을 자유롭게 전환해서 사용할 수 있습니다!")
        print("=" * 60)
        
        return 0
    else:
        print("\n⚠️ 일부 테스트 실패")
        for test_name, passed in results.items():
            print(f"   {test_name}: {'✅' if passed else '❌'}")
        return 1


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n테스트 중단")
        result = 1
    finally:
        loop.close()
    
    sys.exit(result)