#!/usr/bin/env python3
"""
data_prefetch.py .env 로드 테스트
"""
import os
import sys
import logging

# 로거 설정
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

print("🔧 data_prefetch.py .env 로드 테스트")
print("=" * 60)

# 1. 현재 환경 변수 확인
print("1. 현재 환경 변수:")
print(f"   KRX_ID: {os.environ.get('KRX_ID', '없음')}")
print(f"   KRX_PW: {'있음' if os.environ.get('KRX_PW') else '없음'}")

# 2. .env 수동 로드 확인
print("\n2. .env 직접 로드:")
env_path = "/home/leedw/projects/prism-insight/.env"
if os.path.exists(env_path):
    print(f"   ✅ .env 파일 있음: {env_path}")
    
    # 직접 읽기
    with open(env_path, 'r') as f:
        env_lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
    
    # 보안상 전체 보여주지 않음
    env_keys = []
    for line in env_lines:
        if '=' in line:
            key = line.split('=')[0].strip()
            env_keys.append(key)
    
    print(f"   ✅ .env 키: {', '.join(env_keys)}")
    
    # dotenv로 로드
    try:
        from dotenv import load_dotenv
        old_env = dict(os.environ)
        load_dotenv(env_path)
        
        # 변화 확인
        new_krx_id = os.environ.get('KRX_ID')
        if new_krx_id != old_env.get('KRX_ID'):
            print(f"   ✅ dotenv 로드 성공: KRX_ID={new_krx_id[:3]}...")
        else:
            print(f"   ❌ dotenv 로드 실패 (변화 없음)")
    except ImportError:
        print("   ❌ dotenv 모듈 없음")
    except Exception as e:
        print(f"   ❌ dotenv 로드 오류: {e}")
else:
    print(f"   ❌ .env 파일 없음")

# 3. data_prefetch.py 임포트 테스트
print("\n3. data_prefetch.py 임포트 테스트:")
try:
    # data_prefetch.py 위치
    data_prefetch_path = "/home/leedw/projects/prism-insight/cores/data_prefetch.py"
    if os.path.exists(data_prefetch_path):
        print(f"   ✅ data_prefetch.py 있음")
        
        # 임포트
        import importlib.util
        spec = importlib.util.spec_from_file_location("data_prefetch", data_prefetch_path)
        module = importlib.util.module_from_spec(spec)
        
        # sys.modules에 추가
        sys.modules["data_prefetch"] = module
        
        # 환경 변수 초기화 (로드 전)
        original_krx_id = os.environ.get('KRX_ID')
        print(f"   로드 전 KRX_ID: {original_krx_id}")
        
        # 모듈 실행 (이때 .env 로드됨)
        spec.loader.exec_module(module)
        
        # 로드 후 확인
        after_krx_id = os.environ.get('KRX_ID')
        print(f"   로드 후 KRX_ID: {after_krx_id}")
        
        if after_krx_id != original_krx_id:
            print(f"   ✅ data_prefetch.py에서 .env 로드됨")
        else:
            print(f"   ❌ data_prefetch.py .env 로드 안 됨")
            
        # 모듈 함수 확인
        print(f"\n   모듈 함수:")
        for name in dir(module):
            if name.startswith('_') and not name.startswith('__'):
                if hasattr(module, name) and callable(getattr(module, name)):
                    print(f"     - {name}()")
        
        print(f"\n   공개 함수:")
        for name in dir(module):
            if not name.startswith('_'):
                if hasattr(module, name) and callable(getattr(module, name)):
                    print(f"     - {name}()")
        
    else:
        print(f"   ❌ data_prefetch.py 없음")
    
except Exception as e:
    print(f"   ❌ 임포트 오류: {type(e).__name__}: {e}")

# 4. PyKRX 로그인 테스트 (선택적)
print("\n4. PyKRX 로그인 테스트 (원하면 실행):")
run_pykrx_test = input("   PyKRX 로그인 테스트 실행? (y/N): ").strip().lower()

if run_pykrx_test == 'y':
    try:
        from pykrx.website.comm.auth import get_krx_auth
        
        krx_id = os.environ.get('KRX_ID')
        krx_pw = os.environ.get('KRX_PW')
        
        if not krx_id or not krx_pw:
            print(f"   ❌ KRX_ID 또는 KRX_PW 환경 변수 없음")
        else:
            print(f"   로그인 시도: ID={krx_id[:3]}...")
            
            session = get_krx_auth(login_method="krx")
            if session:
                print(f"   ✅ PyKRX 로그인 성공")
            else:
                print(f"   ❌ PyKRX 로그인 실패")
    
    except ImportError:
        print(f"   ❌ PyKRX auth 모듈 없음")
    except Exception as e:
        print(f"   ❌ PyKRX 테스트 오류: {type(e).__name__}: {e}")

print("\n" + "=" * 60)
print("✅ 테스트 완료")

# 결론
print(f"\n📌 결론:")
env_loaded = os.environ.get('KRX_ID') != None
print(f"1. .env 로드 여부: {'성공' if env_loaded else '실패'}")
print(f"2. KRX_ID 설정: {'있음' if os.environ.get('KRX_ID') else '없음'}")
print(f"3. data_prefetch.py 준비: {'완료' if 'module' in locals() else '미완료'}")