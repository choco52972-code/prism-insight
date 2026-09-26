#!/usr/bin/env python3
"""
Macro Intelligence agent — live integration test.

Runs the REAL pipeline end to end and prints progress/data to the screen:
  1) prefetch_macro_intelligence_data()  — real KOSPI/KOSDAQ OHLCV + sector map (pykrx)
  2) create_macro_intelligence_agent()   — build the prompt from prefetched data
  3) OpenAIAugmentedLLM.generate_str()   — real LLM call with perplexity_ask tool access
  4) Parse and pretty-print the resulting JSON

This is NOT a pytest unit test (no test_* function inside) so the normal
`pytest tests/` run does not pick it up, hit the network, or spend API
credits. It mirrors the tests/test_krx_api.py convention: a standalone
script meant to be run directly.

Requires: mcp_agent.secrets.yaml with a working perplexity server + an
OpenAI-compatible model (API key, or PRISM_OPENAI_AUTH_MODE=chatgpt_oauth
in .env — the ChatGPT OAuth proxy is started/stopped automatically, same
as stock_analysis_orchestrator.py does).

Usage:
    python tests/test_macro_intelligence_agent_live.py
    python tests/test_macro_intelligence_agent_live.py --language en
    python tests/test_macro_intelligence_agent_live.py --date 20260101
    python tests/test_macro_intelligence_agent_live.py --prefetch-only   # skip the LLM call
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

# cores/*.py modules log via logging.getLogger(__name__) with no handler of
# their own — without this, their logger.info() calls (prefetch progress,
# regime computation, etc.) are silently dropped instead of reaching the
# screen. Mirrors the StreamHandler setup in stock_analysis_orchestrator.py.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)


def print_section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


async def run(reference_date: str, language: str, prefetch_only: bool) -> bool:
    print_section("STEP 1 — Prefetch (real KOSPI/KOSDAQ data via pykrx)")

    from cores.data_prefetch import prefetch_macro_intelligence_data
    prefetched = prefetch_macro_intelligence_data(reference_date)

    if not prefetched:
        print("FAILED: prefetch returned no data (check kospi_kosdaq server / network)")
        return False

    print(f"Keys retrieved: {list(prefetched.keys())}")
    computed = prefetched.get("computed_regime", {})
    if computed:
        print(f"Computed regime : {computed.get('market_regime')} "
              f"(confidence={computed.get('regime_confidence')}, "
              f"simple_ma={computed.get('simple_ma_regime')})")
        idx = computed.get("index_summary", {})
        print(f"KOSPI 20d trend : {idx.get('kospi_20d_trend')} | "
              f"vs 20d MA: {idx.get('kospi_vs_20d_ma')} | "
              f"2w change: {idx.get('kospi_2w_change_pct')}%")
    sector_map = prefetched.get("sector_map", {})
    print(f"Sector map      : {len(sector_map)} tickers")

    if prefetch_only:
        print("\n--prefetch-only set: skipping the LLM call.")
        return True

    print_section("STEP 2 — Build agent prompt")

    from cores.agents.macro_intelligence_agent import create_macro_intelligence_agent
    agent = create_macro_intelligence_agent(reference_date, language, prefetched_data=prefetched)
    print(f"Agent name      : {agent.name}")
    print(f"Instruction size: {len(agent.instruction)} chars")

    print_section("STEP 3 — Run real LLM call (perplexity_ask + OpenAI-compatible model)")

    from mcp_agent.app import MCPApp
    from mcp_agent.workflows.llm.augmented_llm import RequestParams
    from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM

    macro_app = MCPApp(name="macro_intelligence_live_test")
    async with macro_app.run() as macro_run_context:
        run_logger = macro_run_context.logger
        run_logger.info("Macro intelligence live test starting...")

        # Re-attach the agent to this app's context (created above, outside the app run)
        llm = await agent.attach_llm(OpenAIAugmentedLLM)
        message = (
            f"{reference_date} 기준 한국 주식시장 거시경제 분석을 수행하고 JSON으로 출력하세요."
            if language == "ko" else
            f"Perform a macro intelligence analysis of the Korean stock market as of {reference_date} "
            f"and output JSON."
        )
        result = await llm.generate_str(
            message=message,
            request_params=RequestParams(
                model="gpt-5.4-mini",
                reasoning_effort="none",
                maxTokens=16000,
                parallel_tool_calls=True,
                use_history=True,
            ),
        )

    print(f"Raw output ({len(result)} chars):")
    print("-" * 70)
    print(result)
    print("-" * 70)

    print_section("STEP 4 — Parse JSON")
    try:
        macro_data = json.loads(result.strip())
    except json.JSONDecodeError:
        import re
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", result, re.DOTALL)
        macro_data = json.loads(match.group(1).strip()) if match else None

    if not macro_data:
        print("FAILED: could not parse JSON from agent output")
        return False

    print(json.dumps(macro_data, indent=2, ensure_ascii=False))

    required_keys = (
        "analysis_date", "market", "market_regime", "regime_confidence",
        "regime_rationale", "simple_ma_regime", "index_summary",
        "leading_sectors", "lagging_sectors", "risk_events",
        "beneficiary_themes", "report_prose",
    )
    missing = [k for k in required_keys if k not in macro_data]
    if missing:
        print(f"FAILED: missing keys in parsed output: {missing}")
        return False

    print("\nAll required keys present.")
    return True


async def main() -> int:
    parser = argparse.ArgumentParser(description="Macro Intelligence agent live integration test")
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"),
                         help="Reference date, YYYYMMDD (default: today)")
    parser.add_argument("--language", default="ko", choices=["ko", "en"])
    parser.add_argument("--prefetch-only", action="store_true",
                         help="Only run the data prefetch step; skip the real LLM call")
    parser.add_argument("--no-proxy", action="store_true",
                         help="Skip ChatGPT OAuth proxy even if PRISM_OPENAI_AUTH_MODE=chatgpt_oauth")
    args = parser.parse_args()

    import os
    proxy_started = False
    if not args.no_proxy and os.getenv("PRISM_OPENAI_AUTH_MODE") == "chatgpt_oauth":
        try:
            from cores.chatgpt_proxy import inject_env, start_proxy
            inject_env()
            proxy_started = await start_proxy()
            print(f"ChatGPT OAuth proxy started: {proxy_started}")
        except Exception as e:
            print(f"ChatGPT OAuth proxy setup failed, falling back to standard API: {e}")

    try:
        ok = await run(args.date, args.language, args.prefetch_only)
    except Exception as e:
        print_section("ERROR")
        print(f"{type(e).__name__}: {e}")
        ok = False
    finally:
        if proxy_started:
            try:
                from cores.chatgpt_proxy import stop_proxy
                await stop_proxy()
            except Exception:
                pass

    print_section("RESULT")
    print("PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
