#!/usr/bin/env python3
"""
간단한 afternoon 모드 테스트
"""
import os
import sys

print("Afternoon 모드 실행 테스트")
print("=" * 40)

# 1. orchestrator 존재 확인
orchestrator = '/home/leedw/projects/prism-insight/stock_analysis_orchestrator.py'
if not os.path.exists(orchestrator):
    print(f"❌ orchestrator 없음: {orchestrator}")
    sys.exit(1)

print(f"✅ orchestrator: {orchestrator}")

# 2. 실행 명령어
cmd = f'cd /home/leedw/projects/prism-insight && python3 stock_analysis_orchestrator.py afternoon'

print(f"\n실행 명령어: {cmd}")
print("\n⚠️ 실행 중... (로그 파일: /tmp/orchestrator_simple.log)")

# 3. 실행
import subprocess
import time

log_file = '/tmp/orchestrator_simple.log'

try:
    start_time = time.time()
    
    with open(log_file, 'w') as log_f:
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        print("실행 중...")
        # 타임아웃 설정 (5분)
        timeout = 300  # 5분
        elapsed = 0
        
        while process.poll() is None and elapsed < timeout:
            time.sleep(5)
            elapsed += 5
            print(f"진행 중: {elapsed}초...")
        
        if elapsed >= timeout:
            print("⏱️ 타임아웃 (5분 초과)")
            process.terminate()
            time.sleep(2)
            if process.poll() is None:
                process.kill()
        
        return_code = process.wait()
        end_time = time.time()
        
        duration = end_time - start_time
        print(f"\n실행 완료")
        print(f"실행 시간: {duration:.1f}초")
        print(f"종료 코드: {return_code}")
        
except Exception as e:
    print(f"❌ 실행 오류: {e}")
    return_code = -1

# 4. 로그 분석
print("\n" + "=" * 40)
print("로그 분석")
print("=" * 40)

if os.path.exists(log_file):
    with open(log_file, 'r') as f:
        lines = f.readlines()
    
    print(f"총 라인 수: {len(lines)}")
    
    # 에러/경고 검색
    errors = []
    warnings = []
    
    for i, line in enumerate(lines, 1):
        line_stripped = line.strip()
        line_lower = line_stripped.lower()
        
        # 중요한 에러 패턴
        if ('error' in line_lower and 'INFO' not in line_stripped) or \
           'KeyError' in line_stripped or \
           'JSONDecodeError' in line_stripped or \
           'Exception' in line_stripped:
            errors.append((i, line_stripped))
        elif 'warn' in line_lower or 'WARNING' in line_stripped:
            warnings.append((i, line_stripped))
    
    # 결과 출력
    print(f"\n에러 발견: {len(errors)}개")
    if errors:
        print("🔴 에러 목록:")
        for line_num, error_line in errors[:10]:  # 처음 10개만
            print(f"  {line_num:4d}: {error_line}")
        if len(errors) > 10:
            print(f"  ... 외 {len(errors)-10}개 에러")
    else:
        print("✅ 에러 없음")
    
    print(f"\n경고 발견: {len(warnings)}개")
    if warnings:
        print("⚠️ 경고 목록:")
        for line_num, warning_line in warnings[:5]:  # 처음 5개만
            print(f"  {line_num:4d}: {warning_line}")
        if len(warnings) > 5:
            print(f"  ... 외 {len(warnings)-5}개 경고")
    else:
        print("✅ 경고 없음")
    
    # 마지막 20줄
    print(f"\n마지막 20줄:")
    print("-" * 40)
    for line in lines[-20:]:
        print(line.rstrip())
    
    # PyKRX 관련 에러 체크
    print(f"\nPyKRX 관련 검사:")
    pykrx_errors = []
    for i, line in enumerate(lines, 1):
        if any(keyword in line for keyword in ['KRX', '종가', '20260513', 'KOSPI', 'KOSDAQ', 'sector']):
            pykrx_errors.append((i, line.strip()))
    
    if pykrx_errors:
        print("⚠️ PyKRX 관련 메시지:")
        for i, line in pykrx_errors[:10]:
            print(f"  {i:4d}: {line}")
    else:
        print("✅ PyKRX 관련 메시지 없음")
    
else:
    print(f"❌ 로그 파일 없음: {log_file}")

print("\n" + "=" * 40)
print("분석 완료")
print("=" * 40)

print(f"\n로그 파일: {log_file}")
print(f"종료 코드: {return_code}")

if return_code == 0:
    print("✅ 스크립트 정상 종료")
else:
    print(f"❌ 스크립트 비정상 종료")