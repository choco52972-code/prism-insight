#!/usr/bin/env python3
"""
Prism Insight 브로커 기본 기능 테스트
KIS와 Kiwoom 둘 다 설정을 통해 사용 가능한지 확인
"""

import asyncio
import sys
from pathlib import Path

# 프로젝트 경로 추가
prism_insight_path = Path(__file__).parent
sys.path.insert(0, str(prism_insight_path))

print("🔧 Prism Insight 브로커 기본 기능 테스트")
print("=" * 60)


async def test_imports():
    """모듈 임포트 테스트"""
    print("\n1️⃣ 모듈 임포트 테스트")
    
    success = True
    
    # KIS 모듈
    try:
        from trading.brokers.kis import KisAuth, KisTrading
        print(f"✅ KIS 모듈: KisAuth, KisTrading")
    except Exception as e:
        print(f"❌ KIS 모듈 실패: {e}")
        success = False
    
    # Kiwoom 모듈
    try:
        from trading.brokers.kiwoom import KiwoomAuth, KiwoomTrading
        print(f"✅ Kiwoom 모듈: KiwoomAuth, KiwoomTrading")
    except Exception as e:
        print(f"❌ Kiwoom 모듈 실패: {e}")
        success = False
    
    # 팩토리
    try:
        from trading import BrokerFactory, BrokerType, BrokerConfig
        print(f"✅ 팩토리: BrokerFactory, BrokerType")
    except Exception as e:
        print(f"❌ 팩토리 모듈 실패: {e}")
        success = False
    
    return success


async def test_broker_creation():
    """브로커 생성 테스트"""
    print("\n2️⃣ 브로커 생성 테스트")
    
    success = True
    from trading import BrokerFactory, BrokerType, BrokerConfig
    
    factory = BrokerFactory()
    print(f"✅ BrokerFactory 생성: {factory}")
    
    # Kiwoom 생성
    try:
        kiwoom_config = BrokerConfig(
            broker_type=BrokerType.KIWOOM,
            trading_mode="mock",
            config={"mode": "mock", "account_no": "81203640"}
        )
        kiwoom_auth, kiwoom_trading = factory.create_broker(BrokerType.KIWOOM, kiwoom_config)
        print(f"✅ Kiwoom 브로커 생성: {kiwoom_auth.__class__.__name__}")
        
        # 간단한 작업
        token = await kiwoom_auth.get_token()
        print(f"   토큰: {token if token else '(모의 모드)'}")
        
        await kiwoom_trading.close()
        
    except Exception as e:
        print(f"❌ Kiwoom 생성 실패: {e}")
        success = False
    
    # KIS 생성
    try:
        kis_config = BrokerConfig(
            broker_type=BrokerType.KIS,
            trading_mode="mock",
            config={"mode": "mock", "account_no": "1234567890"}
        )
        kis_auth, kis_trading = factory.create_broker(BrokerType.KIS, kis_config)
        print(f"✅ KIS 브로커 생성: {kis_auth.__class__.__name__}")
        
        # 간단한 작업
        token = await kis_auth.get_token()
        print(f"   토큰: {token if token else '(Mock 모드)'}")
        
        await kis_trading.close()
        
    except Exception as e:
        print(f"❌ KIS 생성 실패: {e}")
        success = False
    
    return success


def test_config_files():
    """설정 파일 테스트"""
    print("\n3️⃣ 설정 파일 테스트")
    
    success = True
    
    # KIS 설정 파일
    kis_config_path = Path(prism_insight_path) / "trading" / "brokers" / "kis" / "config" / "kis_config.yaml"
    if kis_config_path.exists():
        import yaml
        with open(kis_config_path, 'r', encoding='utf-8') as f:
            kis_config = yaml.safe_load(f)
        print(f"✅ KIS 설정 파일: {kis_config_path.name}")
        print(f"   모드: {kis_config.get('mode', 'N/A')}")
        print(f"   계좌: {len(kis_config.get('accounts', []))}개")
    else:
        print(f"❌ KIS 설정 파일 없음: {kis_config_path}")
        success = False
    
    # Kiwoom 설정 파일
    kiwoom_config_path = Path(prism_insight_path) / "trading" / "brokers" / "kiwoom" / "config" / "kiwoom_config.yaml"
    if kiwoom_config_path.exists():
        import yaml
        with open(kiwoom_config_path, 'r', encoding='utf-8') as f:
            kiwoom_config = yaml.safe_load(f)
        print(f"✅ Kiwoom 설정 파일: {kiwoom_config_path.name}")
        print(f"   모드: {kiwoom_config.get('mode', 'N/A')}")
        print(f"   계좌: {len(kiwoom_config.get('accounts', []))}개")
    else:
        print(f"❌ Kiwoom 설정 파일 없음: {kiwoom_config_path}")
        success = False
    
    return success


async def main():
    """메인 테스트"""
    print("Prism Insight 브로커 시스템 기본 테스트\n")
    
    results = {}
    
    # 1. 임포트 테스트
    results['imports'] = await test_imports()
    
    # 2. 브로커 생성 테스트
    results['creation'] = await test_broker_creation()
    
    # 3. 설정 파일 테스트
    results['config_files'] = test_config_files()
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("📊 테스트 결과 요약")
    print("=" * 60)
    
    success_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    
    print(f"✅ 성공: {success_count}/{total_count}")
    print(f"❌ 실패: {total_count - success_count}/{total_count}")
    
    if success_count == total_count:
        print("\n🎉 Prism Insight 브로커 시스템 준비 완료!")
        print("KIS와 Kiwoom을 설정을 통해 선택적으로 사용할 수 있습니다.")
        
        print("\n📝 사용 방법:")
        print("""
1. 설정 파일 편집:
   • KIS: trading/brokers/kis/config/kis_config.yaml
   • Kiwoom: trading/brokers/kiwoom/config/kiwoom_config.yaml

2. 브로커 생성 (Kiwoom 예시):
   ```
   from trading import BrokerFactory, BrokerType, BrokerConfig
   
   factory = BrokerFactory()
   config = BrokerConfig(
       broker_type=BrokerType.KIWOOM,
       trading_mode="mock",
       config={"mode": "mock"}
   )
   
   auth, trading = factory.create_broker(BrokerType.KIWOOM, config)
   ```

3. KIS 사용:
   • 설정 파일에서 mode: "real"로 변경
   • API 키 입력 (실제 KIS 라이브러리 필요)
        """)
        
        return 0
    else:
        print("\n⚠️ 일부 테스트 실패, 확인 필요")
        return 1


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(main())
    except Exception as e:
        print(f"\n❌ 테스트 오류: {e}")
        import traceback
        traceback.print_exc()
        result = 1
    finally:
        loop.close()
    
    sys.exit(result)