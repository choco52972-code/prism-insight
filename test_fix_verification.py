#!/usr/bin/env python3
"""
수정된 코드 테스트
"""
import os
import sys

print("🔧 수정된 코드 테스트")
print("=" * 60)

# 환경 변수 설정 (PyKRX v1.2.8 요구)
os.environ['KRX_ID'] = 'choco529'
os.environ['KRX_PW'] = 'ehddn29!'

print("1. 환경 변수 설정 확인:")
print(f"   KRX_ID: {os.environ.get('KRX_ID')}")
print(f"   KRX_PW: {'*' * len(os.environ.get('KRX_PW', ''))}")

# 2. MCP 서버 모듈 임포트
print("\n2. MCP 서버 모듈 임포트:")
try:
    sys.path.insert(0, "/home/leedw/projects/kospi-kosdaq-stock-server")
    import kospi_kosdaq_stock_server as server
    print(f"   ✅ 모듈 임포트 성공")
    
    # 모듈 내용 확인
    print(f"   모듈 함수 목록:")
    for name in dir(server):
        if not name.startswith('_'):
            print(f"     - {name}")
    
except ImportError as e:
    print(f"   ❌ 모듈 임포트 실패: {e}")
    sys.exit(1)

# 3. _get_krx_client() 함수 확인
print("\n3. _get_krx_client() 함수 확인:")
try:
    client = server._get_krx_client()
    if client:
        print(f"   ✅ PyKRX 클라이언트 생성 성공")
        print(f"   클라이언트 타입: {type(client)}")
    else:
        print(f"   ❌ PyKRX 클라이언트 생성 실패")
except Exception as e:
    print(f"   ❌ _get_krx_client() 오류: {type(e).__name__}: {e}")

# 4. get_sector_info() 함수 테스트
print("\n4. get_sector_info() 함수 테스트:")
date = '20260513'
market = 'KOSPI'

print(f"   호출: get_sector_info('{market}', '{date}')")

try:
    result = server.get_sector_info(market, date)
    print(f"   ✅ 호출 성공!")
    
    print(f"\n5. 결과 분석:")
    print(f"   결과 타입: {type(result)}")
    
    if isinstance(result, dict):
        print(f"   📌 dict 반환됨 (올바름)")
        print(f"   dict 길이: {len(result)}")
        
        if result:
            print(f"   샘플 5개:")
            items = list(result.items())[:5]
            for ticker, sector in items:
                print(f"     {ticker}: {sector}")
            
            print(f"\n   검증:")
            print(f"     - 6자리 종목코드: {'예' if all(len(k) == 6 for k in result.keys()) else '아니오'}")
            print(f"     - 타입 일치: {'예' if isinstance(result, dict) else '아니오'}")
            
            # data_prefetch.py 호환성 테스트
            print(f"\n   data_prefetch.py 호환성:")
            from collections.abc import Mapping
            if isinstance(result, Mapping) and "error" not in result:
                print(f"     ✅ data_prefetch.py가 기대하는 dict 타입 일치")
                print(f"     ✅ 'error' 키 없음 (정상)")
            else:
                print(f"     ⚠️ data_prefetch.py와 호환성 문제")
                
        else:
            print(f"   ⚠️ 빈 dict 반환됨")
            
    else:
        print(f"   ❌ dict가 아님: {type(result)}")
        print(f"   ⚠️ data_prefetch.py 호환성 문제!")
    
except Exception as e:
    print(f"   ❌ 호출 실패: {type(e).__name__}: {e}")
    import traceback
    print(f"   트레이스백:")
    for line in traceback.format_exc().split('\n')[-5:]:
        print(f"     {line}")

# 6. PyKRX 직접 테스트
print("\n6. PyKRX 직접 테스트:")
try:
    from pykrx import stock
    print(f"   PyKRX 버전: {stock.__version__}")
    
    # 직접 호출
    df = stock.get_market_sector_classifications(date, market)
    if df is not None and not df.empty:
        print(f"   ✅ PyKRX 직접 호출 성공")
        print(f"     모양: {df.shape}")
        print(f"     컬럼: {list(df.columns)}")
        
        # 컬럼명 확인
        print(f"\n   컬럼 분석:")
        for col in df.columns:
            print(f"     - {col}")
        
        # '종목코드', '업종명' 컬럼 확인
        has_ticker = '종목코드' in df.columns
        has_sector = '업종명' in df.columns
        print(f"\n   변환 가능성:")
        print(f"     종목코드 컬럼: {'있음' if has_ticker else '없음'}")
        print(f"     업종명 컬럼: {'있음' if has_sector else '없음'}")
        print(f"     DataFrame → dict 변환: {'가능' if has_ticker and has_sector else '불가능'}")
        
    else:
        print(f"   ⚠️ PyKRX 빈 데이터")
        
except Exception as e:
    print(f"   ❌ PyKRX 직접 호출 실패: {type(e).__name__}: {e}")

print("\n" + "=" * 60)
print("✅ 테스트 완료")

# 결론
print(f"\n📌 최종 결론:")
print(f"1. get_sector_info() 반환 타입: {type(result).__name__ if 'result' in locals() else 'N/A'}")
print(f"2. data_prefetch.py 기대 타입: dict")
print(f"3. 일치 여부: {'일치' if isinstance(result, dict) else '불일치'}")
print(f"4. WARNING 해결: {'해결됨' if isinstance(result, dict) and result else '미해결'}")