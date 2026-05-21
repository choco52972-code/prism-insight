#!/usr/bin/env python3
"""
PyKRX v1.2.8 최종 로그인 테스트
"""
import os
import sys

print("🔧 PyKRX v1.2.8 최종 로그인 테스트")
print("=" * 60)

# 1. .env 로드
print("1. .env 로드:")
env_path = "/home/leedw/projects/prism-insight/.env"
if os.path.exists(env_path):
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
        print(f"   ✅ .env 로드 완료")
        
        # 환경 변수 확인
        krx_id = os.environ.get('KRX_ID')
        krx_pw = os.environ.get('KRX_PW')
        
        if krx_id and krx_pw:
            print(f"   ✅ KRX_ID: {krx_id[:3]}...")
            print(f"   ✅ KRX_PW: {'*' * len(krx_pw)}")
        else:
            print(f"   ❌ KRX_ID/KRX_PW 없음")
            
    except ImportError:
        print(f"   ❌ dotenv 모듈 없음")
else:
    print(f"   ❌ .env 파일 없음")

# 2. MCP 서버 모듈 테스트
print("\n2. MCP 서버 로그인 테스트:")
try:
    sys.path.insert(0, "/home/leedw/projects/kospi-kosdaq-stock-server")
    import kospi_kosdaq_stock_server as server
    
    print(f"   ✅ 모듈 임포트 성공")
    
    # _get_krx_client() 테스트
    try:
        client = server._get_krx_client()
        if client:
            print(f"   ✅ PyKRX 클라이언트 생성 성공")
        else:
            print(f"   ❌ PyKRX 클라이언트 생성 실패")
    except Exception as e:
        print(f"   ❌ _get_krx_client() 오류: {e}")
    
    # get_sector_info() 테스트
    print(f"\n3. get_sector_info('KOSPI', '20260513') 호출:")
    try:
        result = server.get_sector_info('KOSPI', '20260513')
        
        print(f"   ✅ 호출 성공")
        print(f"   결과 타입: {type(result)}")
        
        if isinstance(result, dict):
            print(f"   📌 dict 반환됨")
            print(f"   dict 길이: {len(result)}")
            
            if result:
                print(f"   ✅ 데이터 있음 ({len(result)}종목)")
                
                # 샘플 출력
                items = list(result.items())[:3]
                for ticker, sector in items:
                    print(f"     {ticker}: {sector}")
                
                print(f"\n   검증:")
                print(f"     - 모든 키가 6자리: {'예' if all(len(k) == 6 for k in result.keys()) else '아니오'}")
                print(f"     - 중복 없음: {'예' if len(result) == len(set(result.keys())) else '아니오'}")
                print(f"     - data_prefetch.py 호환성: {'완벽' if isinstance(result, dict) and 'error' not in result else '주의'}")
                
                # PyKRX v1.2.8 정상 동작 확인
                print(f"\n   ✅ PyKRX v1.2.8 로그인 성공!")
                print(f"   ✅ 데이터 정상 수신 완료!")
                print(f"   ✅ data_prefetch.py 호환 가능!")
                
            else:
                print(f"   ⚠️ 빈 dict 반환됨")
                
                # PyKRX 직접 확인
                print(f"\n   PyKRX 직접 확인:")
                try:
                    from pykrx import stock
                    df = stock.get_market_sector_classifications('20260513', 'KOSPI')
                    if df is not None:
                        print(f"     PyKRX DataFrame: {df.shape if not df.empty else '빈 DataFrame'}")
                        print(f"     컬럼: {list(df.columns) if not df.empty else '없음'}")
                    else:
                        print(f"     ❌ PyKRX도 데이터 없음")
                except Exception as e:
                    print(f"     ❌ PyKRX 오류: {type(e).__name__}: {e}")
                
        else:
            print(f"   ❌ dict가 아님: {type(result)}")
            
    except Exception as e:
        print(f"   ❌ get_sector_info() 오류: {type(e).__name__}: {e}")
        import traceback
        tb = traceback.extract_tb(e.__traceback__)[-3:]
        for frame in tb:
            print(f"     {frame.filename}:{frame.lineno} in {frame.name}")
            print(f"       {frame.line or ''}")
    
except ImportError as e:
    print(f"   ❌ 모듈 임포트 실패: {e}")

# 4. PyKRX 직접 테스트
print("\n4. PyKRX 직접 로그인 테스트:")
test_pykrx = input("   직접 PyKRX 로그인 테스트 실행? (y/N): ").strip().lower()

if test_pykrx == 'y':
    try:
        from pykrx.website.comm.auth import get_krx_auth
        
        krx_id = os.environ.get('KRX_ID')
        krx_pw = os.environ.get('KRX_PW')
        
        if not krx_id or not krx_pw:
            print(f"   ❌ 환경 변수 없음")
        else:
            print(f"   로그인 시도 중...")
            
            session = get_krx_auth(login_method="krx")
            if session:
                print(f"   ✅ PyKRX 직접 로그인 성공")
                
                # 데이터 가져오기
                from pykrx import stock
                df = stock.get_market_sector_classifications('20260513', 'KOSPI')
                print(f"   데이터 수신: {df.shape if df is not None and not df.empty else '없음'}")
                if df is not None and not df.empty:
                    print(f"   컬럼: {list(df.columns)}")
            else:
                print(f"   ❌ PyKRX 직접 로그인 실패")
    
    except ImportError:
        print(f"   ❌ PyKRX auth 모듈 없음")
    except Exception as e:
        print(f"   ❌ PyKRX 테스트 오류: {e}")

print("\n" + "=" * 60)
print("✅ 최종 테스트 완료")

# 결론
print(f"\n📌 최종 결론:")
if 'result' in locals():
    result_type = type(result).__name__
    result_len = len(result) if isinstance(result, dict) else 0
    print(f"1. get_sector_info() 반환: {result_type} ({result_len}개)")
    print(f"2. PyKRX v1.2.8 로그인: {'성공' if result_len > 0 else '실패'}")
    print(f"3. data_prefetch.py 호환: {'완료' if isinstance(result, dict) else '문제'}")
    print(f"4. WARNING 해결: {'완료' if result_len > 0 else '미해결'}")
else:
    print("❌ 테스트 도중 오류 발생")