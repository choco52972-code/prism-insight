#!/usr/bin/env python3
"""
PRISM-INSIGHT Demo Script

Generate a single AI-powered stock analysis report (PDF).
No Telegram, no trading - just the analysis.

Usage:
    python demo.py                    # Analyze Apple (AAPL)
    python demo.py MSFT               # Analyze Microsoft
    python demo.py NVDA "NVIDIA Corp" # Analyze with custom company name

Reports are saved to: prism-us/pdf_reports/
"""
import asyncio
import argparse
import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "prism-us"))
# Add parent directory for mcp_agent module
sys.path.insert(0, str(project_root.parent))

# Import us_analysis module dynamically (prism-us has hyphen in name)
import importlib.util
_us_analysis_path = project_root / "prism-us" / "cores" / "us_analysis.py"
_spec = importlib.util.spec_from_file_location("us_analysis", _us_analysis_path)
us_analysis_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(us_analysis_module)
analyze_us_stock = us_analysis_module.analyze_us_stock


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


def get_company_name(ticker: str) -> str:
    """Get company name from ticker using yfinance."""
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info
        return info.get('longName') or info.get('shortName') or ticker
    except Exception:
        return ticker


async def generate_report(ticker: str, company_name: str, language: str = "ko") -> tuple:
    """
    Generate a stock analysis report.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")
        company_name: Company name (e.g., "Apple Inc.")
        language: Language code ("en" or "ko")

    Returns:
        tuple: (markdown_path, pdf_path)
    """
    # Ensure project root is in sys.path for cores imports (중복 추가 방지)
    import logging
    import sys
    from pathlib import Path
    print(f"GENERATE_REPORT DEBUG: __file__ = {__file__}")
    print(f"GENERATE_REPORT DEBUG: Path(__file__).parent = {Path(__file__).parent}")
    print(f"GENERATE_REPORT DEBUG: sys.path before = {sys.path}")
    project_root = Path(__file__).parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    from report_generator import save_us_report, save_us_pdf_report

    # 프록시 모드 확인
    logging.basicConfig(level=logging.DEBUG)
    import os
    proxy_mode = os.getenv("PRISM_OPENAI_AUTH_MODE", "")
    print(f"DEBUG: proxy_mode = '{proxy_mode}'")
    
    if proxy_mode == "vibeconduit":
        print("=== VibeConduit 프록시 설정 ===")
        os.environ["OPENAI_BASE_URL"] = "http://localhost:8317/v1"
        os.environ["OPENAI_API_KEY"] = ""
        print(f"   OPENAI_BASE_URL={os.environ.get('OPENAI_BASE_URL')}")
        print("   OPENAI_API_KEY=(empty)")
    elif proxy_mode == "chatgpt_oauth" or proxy_mode == "claude_oauth":
        try:
            # Add project root to sys.path for this import (중요!)
            project_root = Path(__file__).parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            
            print(f"DEBUG: sys.path = {sys.path}")
            print(f"DEBUG: 프로젝트 루트 = {project_root}")
            print(f"DEBUG: Checking cores directory at {project_root}/cores")
            
            # 프록시 모드에 따라 모듈 이름 결정
            if proxy_mode == "chatgpt_oauth":
                proxy_module_name = "cores.chatgpt_proxy"
                proxy_port = 18741
                proxy_name = "ChatGPT OAuth"
            else:  # claude_oauth
                proxy_module_name = "cores.claude_proxy"
                proxy_port = 18742
                proxy_name = "Claude OAuth"
            
            # importlib를 사용하여 모듈 로드
            import importlib.util
            import sys
            import os
            
            # 모듈 경로 구성
            module_path = os.path.join(str(project_root), "cores", proxy_module_name.split(".")[1], "__init__.py")
            print(f"DEBUG: Trying to load proxy module from: {module_path}")
            print(f"DEBUG: Module path exists: {os.path.exists(module_path)}")
            
            # 명시적으로 모듈 로드
            spec = importlib.util.spec_from_file_location(proxy_module_name, module_path)
            proxy = importlib.util.module_from_spec(spec)
            sys.modules[proxy_module_name] = proxy
            spec.loader.exec_module(proxy)
            
            # 함수 추출
            inject_env = proxy.inject_env
            start_proxy = proxy.start_proxy
            clear_env = proxy.clear_env
            
            print(f"=== {proxy_name} 프록시 설정 ===")
            
            # 1. 환경 변수 강제 설정 (mcp_agent가 이를 사용하도록)
            inject_env()
            print("✅ 환경 변수 설정:")
            print(f"   OPENAI_BASE_URL={os.environ.get('OPENAI_BASE_URL')}")
            if os.environ.get('OPENAI_API_KEY'):
                print("   OPENAI_API_KEY=***")
            else:
                print("   OPENAI_API_KEY=(empty)")
            
            # 2. 프록시 서버가 이미 실행 중인지 확인
            import asyncio
            import aiohttp
            
            async def check_proxy_running():
                try:
                    async with aiohttp.ClientSession() as session:
                        # /health 체크
                        try:
                            async with session.get(f"http://localhost:{proxy_port}/health", timeout=3) as resp:
                                if resp.status == 200:
                                    return True
                        except:
                            pass
                        
                        # /v1/models 체크 (fallback)
                        try:
                            async with session.get(f"http://localhost:{proxy_port}/v1/models", timeout=3) as resp:
                                return resp.status == 200
                        except:
                            return False
                except:
                    return False
            
            # 3. 프록시 실행 상태 확인
            proxy_running = await check_proxy_running()
            
            if not proxy_running:
                print(f"🚀 {proxy_name} 프록시 서버 시작 중...")
                proxy_started = await start_proxy()
                if proxy_started:
                    print(f"✅ {proxy_name} 프록시 서버 시작 성공")
                    
                    # 서버 초기화 대기
                    await asyncio.sleep(2)
                    
                    # 다시 확인
                    proxy_running = await check_proxy_running()
                    if not proxy_running:
                        print(f"⚠️  {proxy_name} 프록시 서버 시작됐지만 응답하지 않음, 표준 API로 폴백")
                        clear_env()
                else:
                    print(f"❌ {proxy_name} 프록시 서버 시작 실패, 표준 API로 폴백")
                    clear_env()
            else:
                print(f"✅ {proxy_name} 프록시 서버 이미 실행 중")
                
        except Exception as e:
            print(f"⚠️  {proxy_name} 프록시 설정 오류: {e}, 표준 API로 폴백")
            import traceback
            traceback.print_exc()
            try:
                if proxy_mode == "chatgpt_oauth":
                    from cores.chatgpt_proxy import clear_env
                else:
                    from cores.claude_proxy import clear_env
                clear_env()
            except:
                pass
    # Check if Perplexity is configured for news analysis
    include_news = check_perplexity_configured()

    print(f"\n{'='*60}")
    print(f"  PRISM-INSIGHT AI Stock Analysis")
    print(f"  Ticker: {ticker}")
    print(f"  Company: {company_name}")
    print(f"  Language: {'English' if language == 'en' else 'Korean'}")
    if not include_news:
        print(f"  Note: News analysis skipped (Perplexity API not configured)")
    print(f"{'='*60}\n")

    print("[1/3] Generating AI analysis report...")
    print("      This may take 3-5 minutes. AI agents are analyzing:")
    print("      - Price & volume trends")
    print("      - Institutional holdings")
    print("      - Financial fundamentals")
    if include_news:
        print("      - Recent news & sentiment")
    print("      - Market conditions")
    print("      - Investment strategy\n")

    start_time = time.time()

    # Debug environment variables
    print(f"DEBUG: OPENAI_BASE_URL = {os.environ.get('OPENAI_BASE_URL')}")
    print(f"DEBUG: OPENAI_API_KEY = {'***' if os.environ.get('OPENAI_API_KEY') else '(empty)'}")
    
    # Generate the report
    reference_date = datetime.now().strftime("%Y%m%d")
    report_content = await analyze_us_stock(
        ticker=ticker,
        company_name=company_name,
        reference_date=reference_date,
        language=language,
        include_news=include_news
    )

    analysis_time = time.time() - start_time
    print(f"\n[2/3] Analysis complete! ({analysis_time:.1f} seconds)")
    print(f"      Report length: {len(report_content):,} characters")

    # Save markdown
    print("[3/3] Saving report files...")
    md_path = save_us_report(ticker, company_name, report_content)

    # Convert to PDF
    pdf_path = save_us_pdf_report(ticker, company_name, md_path)

    return md_path, pdf_path


def main():
    parser = argparse.ArgumentParser(
        description="Generate AI-powered stock analysis report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python demo.py                      # Analyze Apple (AAPL)
  python demo.py MSFT                 # Analyze Microsoft
  python demo.py NVDA "NVIDIA Corp"   # Analyze with custom name
  python demo.py AAPL --language ko   # Korean report
        """
    )
    parser.add_argument(
        "ticker",
        nargs="?",
        default="AAPL",
        help="Stock ticker symbol (default: AAPL)"
    )
    parser.add_argument(
        "company_name",
        nargs="?",
        default=None,
        help="Company name (auto-detected if not provided)"
    )
    parser.add_argument(
        "--language", "-l",
        choices=["ko", "en"],
        default="ko",
        help="Report language (default: ko)"
    )

    args = parser.parse_args()

    ticker = args.ticker.upper()

    # Auto-detect company name if not provided
    if args.company_name:
        company_name = args.company_name
    else:
        print(f"Looking up company name for {ticker}...")
        company_name = get_company_name(ticker)
        print(f"Found: {company_name}")

    try:
        md_path, pdf_path = asyncio.run(
            generate_report(ticker, company_name, args.language)
        )

        print(f"\n{'='*60}")
        print("  Report Generated Successfully!")
        print(f"{'='*60}")
        print(f"\n  Markdown: {md_path}")
        print(f"  PDF:      {pdf_path}")
        print(f"\n  Open the PDF to view your AI-generated analysis report.")
        print(f"\n{'='*60}")

        # Try to open PDF on macOS
        if sys.platform == "darwin":
            print("\nOpening PDF...")
            subprocess.run(["open", str(pdf_path)], check=False)

    except KeyboardInterrupt:
        print("\n\nAnalysis cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()