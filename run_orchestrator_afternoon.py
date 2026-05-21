#!/usr/bin/env python3
"""
afternoon 모드로 orchestrator 실행 및 로그 체크
"""
import sys
import os
import subprocess
import time

print("stock_analysis_orchestrator.py afternoon 모드 실행")
print("=" * 60)

# orchestrator 경로
orchestrator_path = '/home/leedw/projects/prism-insight/stock_analysis_orchestrator.py'

if not os.path.exists(orchestrator_path):
    print(f"❌ orchestrator 파일 없음: {orchestrator_path}")
    sys.exit(1)

# 로그 파일 경로
log_file = '/tmp/orchestrator_afternoon.log'

# 실행 명령어 구성
cmd = f'cd /home/leedw/projects/prism-insight && python3 stock_analysis_orchestrator.py afternoon 2>&1 | tee {log_file}'

print(f"실행 명령어: {cmd}")
print(f"로그 파일: {log_file}")
print("\n⚠️ 실행 중... (몇 분 소요될 수 있습니다)")

# 실행
print("\n" + "-" * 40)
print("실행 시작 시간:", time.strftime("%Y-%m-%d %H:%M:%S"))

try:
    # subprocess 실행
    process = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    # 실시간 출력 및 에러 체크
    error_detected = False
    warning_detected = False
    
    print("실시간 출력:")
    print("-" * 20)
    
    line_count = 0
    error_lines = []
    warning_lines = []
    
    for line in iter(process.stdout.readline, ''):
        line = line.rstrip()
        line_count += 1
        
        # 에러 체크
        if 'error' in line.lower() or 'Error' in line:
            print(f"[ERROR] {line}")
            error_detected = True
            error_lines.append((line_count, line))
        elif 'warn' in line.lower() or 'WARN' in line or 'WARNING' in line:
            print(f"[WARNING] {line}")
            warning_detected = True
            warning_lines.append((line_count, line))
        else:
            # 일반 라인: 처음 몇 줄만 출력
            if line_count <= 20:
                print(f"{line}")
            elif line_count == 21:
                print("... (계속)")
        
        # 특정 에러 패턴 즉시 보고
        if 'KeyError' in line or 'JSONDecodeError' in line or '종가' in line:
            print(f"🔴 CRITICAL ERROR DETECTED: {line}")
            error_detected = True
    
    # 프로세스 완료 대기
    return_code = process.wait()
    
    print("\n" + "-" * 40)
    print("실행 종료 시간:", time.strftime("%Y-%m-%d %H:%M:%S"))
    print(f"종료 코드: {return_code}")
    
    # 결과 분석
    print("\n" + "=" * 60)
    print("실행 결과 분석")
    print("=" * 60)
    
    # 로그 파일 분석
    if os.path.exists(log_file):
        print(f"\n로그 파일 분석: {log_file}")
        
        with open(log_file, 'r') as f:
            all_lines = f.readlines()
        
        print(f"총 라인 수: {len(all_lines)}")
        
        # 에러/경고 통계
        error_count = 0
        warning_count = 0
        
        for i, line in enumerate(all_lines, 1):
            line_lower = line.lower()
            if 'error' in line_lower:
                error_count += 1
            elif 'warn' in line_lower:
                warning_count += 1
        
        print(f"총 에러: {error_count}")
        print(f"총 경고: {warning_count}")
        
        # 중요 에러 출력
        if error_lines:
            print("\n🔴 발견된 에러 라인:")
            for line_num, error_line in error_lines:
                print(f"  라인 {line_num}: {error_line}")
        else:
            print("\n✅ 에러 없음")
        
        # 중요 경고 출력
        if warning_lines:
            print("\n⚠️ 발견된 경고 라인:")
            for line_num, warning_line in warning_lines:
                print(f"  라인 {line_num}: {warning_line}")
        else:
            print("\n✅ 경고 없음")
        
        # 종료 코드 분석
        print(f"\n종료 코드: {return_code}")
        if return_code == 0:
            print("✅ 스크립트 정상 종료")
        else:
            print(f"❌ 스크립트 비정상 종료 (코드: {return_code})")
        
        # 마지막 10줄 출력 (중요)
        print("\n마지막 10줄:")
        print("-" * 40)
        for line in all_lines[-10:]:
            print(line.rstrip())
        
        # PyKRX 관련 특이사항 검사
        print("\nPyKRX 관련 검사:")
        pykrx_issues = []
        for line in all_lines:
            if 'KRX' in line or '종가' in line or 'JSONDecodeError' in line:
                pykrx_issues.append(line.strip())
        
        if pykrx_issues:
            print("⚠️ PyKRX 관련 이슈 발견:")
            for issue in pykrx_issues[:5]:  # 처음 5개만
                print(f"  - {issue}")
        else:
            print("✅ PyKRX 관련 이슈 없음")
    
    # 최종 판단
    print("\n" + "=" * 60)
    print("최종 판단")
    print("=" * 60)
    
    if return_code == 0 and not error_detected:
        print("✅ SUCCESS: stock_analysis_orchestrator.py 정상 실행 완료")
        print("   - KeyError: '20260513' 문제 해결 확인")
        print("   - KeyError: '종가' 문제 해결 확인")
        print("   - PyKRX 버그 수정 효과 확인")
    elif error_detected:
        print("❌ FAILED: 에러가 발견되었습니다")
        print("   - 수정 필요 에러 목록 확인")
    else:
        print("⚠️ WARNING: 경고는 있으나 실행은 완료됨")
    
    print(f"\n로그 파일 위치: {log_file}")
    print(f"로그 크기: {os.path.getsize(log_file) if os.path.exists(log_file) else 0} bytes")

except KeyboardInterrupt:
    print("\n⚠️ 사용자에 의해 중단됨")
    print(f"로그 파일 확인: {log_file}")
except Exception as e:
    print(f"\n❌ 실행 중 오류 발생: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("실행 완료")
print("=" * 60)