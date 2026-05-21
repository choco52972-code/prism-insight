#!/usr/bin/env python3
"""
PRISM-INSIGHT 한국 주식 분석 리포트 데모 스크립트
Generate AI-powered analysis report for Korean stocks.

Usage:
    python kr_demo.py                    # 파두(440110) 분석
    python kr_demo.py 005930             # 삼성전자 분석  
    python kr_demo.py 000660 "SK하이닉스" # SK하이닉스 분석
    python kr_demo.py 440110 --language ko   # 한국어 리포트

Reports are saved to: kr_reports/ and kr_pdf_reports/
"""
import asyncio
import argparse
import sys
import os
import logging
import time
from datetime import datetime
from pathlib import Path

# Add project root to path - adjust order to prioritize cores over prism-us
# Add project root to path
project_root = Path(__file__).parent
import sys
sys.path.insert(0, str(project_root))
# Optional: add prism-us for any US-specific imports
# sys.path.insert(0, str(project_root / "prism-us"))
print(f"sys.path 첫 번째: {sys.path[0]}")
# Import analysis function from cores.main (which re-exports from cores.analysis)
# Import analysis function from cores.analysis
try:
    from cores.analysis import analyze_stock
    print("✓ cores.analysis.analyze_stock 임포트 성공")
except ImportError as e:
    print(f"❌ cores.analysis 임포트 실패: {e}")
    # Fallback dynamic import
    import importlib.util
    analysis_path = project_root / "cores" / "analysis.py"
    if analysis_path.exists():
        spec = importlib.util.spec_from_file_location("cores.analysis", analysis_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        analyze_stock = module.analyze_stock
        print("✓ cores.analysis 동적 로드 성공")
    else:
        print(f"❌ cores/analysis.py 파일을 찾을 수 없음: {analysis_path}")
        sys.exit(1)
from report_generator import save_report, save_pdf_report


def check_perplexity_configured() -> bool:
    """Check if Perplexity API key is configured."""
    import yaml
    config_path = project_root / "mcp_agent.config.yaml"
    if not config_path.exists():
        return False
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        perplexity_key = config.get("mcp", {}).get("servers", {}).get("perplexity", {}).get("env", {}).get("PERPLEXITY_API_KEY", "")
        # Check if it's a real key (not placeholder)
        return perplexity_key and perplexity_key not in ["example key", "", "your-api-key", "YOUR_API_KEY"]
    except Exception:
        return False


def check_krx_configured_and_set_env() -> bool:
    """Load KRX credentials from mcp_agent.config.yaml and set environment variables."""
    import yaml
    import os
    config_path = project_root / "mcp_agent.config.yaml"
    if not config_path.exists():
        print("⚠️  mcp_agent.config.yaml 파일을 찾을 수 없음")
        return False
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        # Get KRX credentials from kospi_kosdaq server config
        krx_config = config.get("mcp", {}).get("servers", {}).get("kospi_kosdaq", {}).get("env", {})
        krx_id = krx_config.get("KRX_ID", "")
        krx_pw = krx_config.get("KRX_PW", "")
        krx_method = krx_config.get("KRX_LOGIN_METHOD", "krx")
        
        if krx_id and krx_pw:
            os.environ["KRX_ID"] = krx_id
            os.environ["KRX_PW"] = krx_pw
            os.environ["KRX_LOGIN_METHOD"] = krx_method
            print(f"✓ KRX 자격증명 설정 완료: ID={krx_id[:3]}...")  # Don't log full ID
            return True
        else:
            print("⚠️  KRX_ID 또는 KRX_PW가 config에 설정되지 않음")
            return False
    except Exception as e:
        print(f"⚠️  KRX 설정 읽기 오류: {e}")
        return False


async def generate_kr_report(ticker: str, company_name: str = None, language: str = "ko", 
                            use_vibeconduit: bool = True) -> tuple:
    """
    Generate Korean stock analysis report.
    
    Args:
        ticker: Stock code (6 digits e.g., '440110', '005930')
        company_name: Company name (optional)
        language: 'ko' or 'en'
        use_vibeconduit: Use vibeconduit proxy (default: True)
    
    Returns:
        tuple: (markdown_path, pdf_path)
    """
    # Set KRX environment variables for data prefetch
    check_krx_configured_and_set_env()
    
    # Set proxy mode
    if use_vibeconduit:
        os.environ["OPENAI_BASE_URL"] = "http://localhost:8317/v1"
        os.environ["OPENAI_API_KEY"] = ""
        print("=== VibeConduit 프록시 설정 ===")
        print(f"   OPENAI_BASE_URL={os.environ.get('OPENAI_BASE_URL')}")
        print("   OPENAI_API_KEY=***")
    else:
        # Try to start ChatGPT OAuth proxy
        try:
            from cores.chatgpt_proxy import start_proxy, inject_env
            proxy_started = await start_proxy()
            if proxy_started:
                inject_env()
                print("=== ChatGPT OAuth 프록시 설정 ===")
                print("   Proxy running on port 18741")
            else:
                print("⚠️  ChatGPT 프록시 시작 실패, 표준 API로 폴백")
        except Exception as e:
            print(f"⚠️  프록시 설정 오류: {e}, 표준 API로 폴백")

    # Check if Perplexity is configured for news analysis
    include_news = check_perplexity_configured()

    print(f"\n{'='*60}")
    print(f"  PRISM-INSIGHT 한국 주식 AI 분석")
    print(f"  종목코드: {ticker}")
    print(f"  회사명: {company_name or '자동감지'}")
    print(f"  언어: {'한국어' if language == 'ko' else 'English'}")
    if not include_news:
        print(f"  참고: 뉴스 분석 생략 (Perplexity API 미설정)")
    print(f"{'='*60}\n")

    print("[1/3] AI 분석 리포트 생성 중...")
    print("      약 3-5분 소요됩니다. AI 에이전트 분석 항목:")
    print("      - 가격 및 거래량 추세")
    print("      - 투자자 매매 동향")
    print("      - 기업 재무제표")
    print("      - 시장 지수 분석")
    if include_news:
        print("      - 최근 뉴스 및 시장 심리")
    print("      - 투자 전략\n")

    start_time = time.time()

    # Debug environment variables
    print(f"디버그: OPENAI_BASE_URL = {os.environ.get('OPENAI_BASE_URL')}")
    print(f"디버그: OPENAI_API_KEY=***")
    
    # Generate the report
    reference_date = datetime.now().strftime("%Y%m%d")
    try:
        report_content = await analyze_stock(
            company_code=ticker,
            company_name=company_name or f"종목_{ticker}",
            reference_date=reference_date,
            language=language
        )
    except Exception as e:
        print(f"\n❌ 리포트 생성 실패: {e}")
        import traceback
        traceback.print_exc()
        return None, None

    analysis_time = time.time() - start_time
    print(f"\n[2/3] 분석 완료! ({analysis_time:.1f} 초)")
    print(f"      리포트 길이: {len(report_content):,} 자")

    # Save markdown
    print("[3/3] 리포트 파일 저장 중...")
    
    # 회사명에 특수문자 제거
    safe_name = (company_name or f"종목_{ticker}").replace(" ", "_").replace(".", "").replace("(", "").replace(")", "")
    
    # 한국 리포트용 디렉토리 생성
    kr_reports_dir = project_root / "kr_reports"
    kr_pdf_dir = project_root / "kr_pdf_reports"
    kr_reports_dir.mkdir(exist_ok=True)
    kr_pdf_dir.mkdir(exist_ok=True)
    
    # 마크다운 저장
    md_filename = f"{ticker}_{safe_name}_{reference_date}_analysis.md"
    md_path = kr_reports_dir / md_filename
    
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    
    print(f"✓ 마크다운 저장 완료: {md_path}")

    # Convert to PDF
    pdf_filename = f"{ticker}_{safe_name}_{reference_date}_analysis.pdf"
    pdf_path = kr_pdf_dir / pdf_filename
    
    try:
        # 직접 pdf_converter 사용
        from pdf_converter import markdown_to_pdf
        markdown_to_pdf(str(md_path), str(pdf_path), method='playwright', add_theme=True)
        pdf_path_final = pdf_path
        print(f"✓ PDF 변환 완료: {pdf_path_final}")
    except Exception as e:
        print(f"⚠️  PDF 변환 실패: {e}")
        import traceback
        traceback.print_exc()
        pdf_path_final = None

    return md_path, pdf_path_final


def main():
    parser = argparse.ArgumentParser(
        description="한국 주식 AI 분석 리포트 생성",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python kr_demo.py                      # 파두(440110) 분석
  python kr_demo.py 005930               # 삼성전자 분석
  python kr_demo.py 000660 "SK하이닉스"   # SK하이닉스 분석
  python kr_demo.py 440110 --language ko # 한국어 리포트
        """
    )
    parser.add_argument(
        "ticker",
        nargs="?",
        default="440110",
        help="주식 종목코드 (6자리 숫자, 기본값: 440110)"
    )
    parser.add_argument(
        "company_name",
        nargs="?",
        default="파두",  # 파두 기본값
        help="회사명 (기본값: '파두')"
    )
    parser.add_argument(
        "--language", "-l",
        choices=["ko", "en"],
        default="ko",
        help="리포트 언어 (기본값: ko)"
    )
    parser.add_argument(
        "--no-proxy",
        action="store_true",
        help="vibeconduit 프록시 사용 안함 (직접 OpenAI API 사용)"
    )

    args = parser.parse_args()

    # Run async function
    md_path, pdf_path = asyncio.run(
        generate_kr_report(
            ticker=args.ticker,
            company_name=args.company_name,
            language=args.language,
            use_vibeconduit=not args.no_proxy
        )
    )

    if md_path:
        print(f"\n{'='*60}")
        print(f"  리포트 생성 성공!")
        print(f"  마크다운: {md_path}")
        if pdf_path:
            print(f"  PDF: {pdf_path}")
        print(f"{'='*60}\n")
        
        # PDF 파일이 있으면 사용자에게 전송 준비
        if pdf_path and pdf_path.exists():
            print(f"✓ PDF 파일이 생성되었습니다: {pdf_path}")
            print("메신저로 전송 가능합니다.")
        elif pdf_path:
            print(f"⚠️  PDF 파일 생성 실패, 마크다운 파일만 확인하세요.")
    else:
        print(f"\n❌ 리포트 생성 실패")


if __name__ == "__main__":
    main()
