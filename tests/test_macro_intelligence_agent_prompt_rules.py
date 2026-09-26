"""Prompt-rule regression tests for the Macro Intelligence agent.

These tests lock down the structural invariants of the macro intelligence
prompt: identity, the prefetch -> schema substitution pipeline (regime,
index_summary, sector taxonomy), and the JSON output contract — so future
edits cannot silently break the programmatic-prefetch integration or leak
internal fields into the schema.

Tests assert *prompt content*, not LLM output — they catch unintended prompt
drift, not modeling regressions.
"""

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from cores.agents.macro_intelligence_agent import (
    create_macro_intelligence_agent,
    _format_index_summary,
)


SAMPLE_PREFETCHED = {
    "computed_regime": {
        "market_regime": "moderate_bull",
        "regime_confidence": 0.72,
        "simple_ma_regime": "bull",
        "index_summary": {
            "kospi_20d_trend": "up",
            "kospi_vs_20d_ma": "above",
            "kospi_2w_change_pct": 3.5,
            "kospi_current": 2650.5,
            "kospi_20d_ma": 2600.0,
            "kosdaq_20d_trend": "up",
        },
    },
    "kospi_ohlcv_md": "| date | close |\n|---|---|\n| 20260101 | 2600 |",
    "kosdaq_ohlcv_md": "| date | close |\n|---|---|\n| 20260101 | 850 |",
    "sector_map": {"005930": "전기·전자", "000660": "전기·전자", "035420": "IT 서비스"},
}


# --- Agent metadata ---------------------------------------------------------

def test_agent_name_and_server():
    agent = create_macro_intelligence_agent(reference_date="20260101")
    assert agent.name == "macro_intelligence_agent"
    assert agent.server_names == ["perplexity"]


# --- Identity / language ----------------------------------------------------

def test_identity_ko():
    agent = create_macro_intelligence_agent(reference_date="20260101", language="ko")
    assert "거시경제 인텔리전스 애널리스트" in agent.instruction
    assert "20260101" in agent.instruction


def test_identity_en():
    agent = create_macro_intelligence_agent(reference_date="20260101", language="en")
    assert "macro intelligence analyst" in agent.instruction
    assert "20260101" in agent.instruction


# --- Perplexity single-call constraint --------------------------------------

def test_perplexity_query_ko():
    agent = create_macro_intelligence_agent(reference_date="20260101", language="ko")
    assert "perplexity_ask 도구를 사용하여" in agent.instruction
    assert "20260101 한국 증시 거시경제 동향" in agent.instruction


def test_perplexity_query_en():
    agent = create_macro_intelligence_agent(reference_date="20260101", language="en")
    assert "Use the perplexity_ask tool" in agent.instruction
    assert "20260101 Korean stock market macro trends" in agent.instruction


# --- Precomputed regime injection (language-agnostic block) ----------------

def test_no_prefetched_data_omits_regime_and_index_context():
    agent = create_macro_intelligence_agent(reference_date="20260101", language="ko")
    assert "Pre-Computed Market Regime" not in agent.instruction
    assert "Pre-fetched Index Data" not in agent.instruction


def test_prefetched_regime_context_present_ko():
    agent = create_macro_intelligence_agent(
        reference_date="20260101", language="ko", prefetched_data=SAMPLE_PREFETCHED)
    assert "Pre-Computed Market Regime (from actual index data)" in agent.instruction
    assert "You may adjust regime_confidence (±0.1)" in agent.instruction
    assert "DO NOT change market_regime unless" in agent.instruction


def test_prefetched_regime_context_present_en():
    agent = create_macro_intelligence_agent(
        reference_date="20260101", language="en", prefetched_data=SAMPLE_PREFETCHED)
    assert "Pre-Computed Market Regime (from actual index data)" in agent.instruction
    assert "You may adjust regime_confidence (±0.1)" in agent.instruction


def test_regime_context_is_language_agnostic():
    # The pre-computed regime block is built once outside the language branch —
    # it must render identically (in English) for both ko and en agents.
    agent_ko = create_macro_intelligence_agent(
        reference_date="20260101", language="ko", prefetched_data=SAMPLE_PREFETCHED)
    agent_en = create_macro_intelligence_agent(
        reference_date="20260101", language="en", prefetched_data=SAMPLE_PREFETCHED)
    assert "KOSPI 20d trend" in agent_ko.instruction
    assert "KOSPI 20d trend" in agent_en.instruction


def test_prefetched_index_data_markdown_included():
    agent = create_macro_intelligence_agent(
        reference_date="20260101", language="ko", prefetched_data=SAMPLE_PREFETCHED)
    assert "## Pre-fetched Index Data" in agent.instruction
    assert "| 20260101 | 2600 |" in agent.instruction
    assert "| 20260101 | 850 |" in agent.instruction


# --- Schema substitution from computed_regime -------------------------------

def test_schema_uses_defaults_without_prefetched_data():
    agent = create_macro_intelligence_agent(reference_date="20260101", language="ko")
    assert '"market_regime": "sideways"' in agent.instruction
    assert '"regime_confidence": 0.5' in agent.instruction
    assert '"simple_ma_regime": "sideways"' in agent.instruction


def test_schema_reflects_prefetched_regime_values_ko():
    agent = create_macro_intelligence_agent(
        reference_date="20260101", language="ko", prefetched_data=SAMPLE_PREFETCHED)
    assert '"market_regime": "moderate_bull"' in agent.instruction
    assert '"regime_confidence": 0.72' in agent.instruction
    assert '"simple_ma_regime": "bull"' in agent.instruction


def test_schema_reflects_prefetched_regime_values_en():
    agent = create_macro_intelligence_agent(
        reference_date="20260101", language="en", prefetched_data=SAMPLE_PREFETCHED)
    assert '"market_regime": "moderate_bull"' in agent.instruction
    assert '"regime_confidence": 0.72' in agent.instruction
    assert '"simple_ma_regime": "bull"' in agent.instruction


def test_schema_index_summary_matches_formatted_helper():
    agent = create_macro_intelligence_agent(
        reference_date="20260101", language="ko", prefetched_data=SAMPLE_PREFETCHED)
    expected = _format_index_summary(SAMPLE_PREFETCHED)
    assert f'"index_summary": {expected}' in agent.instruction


# --- _format_index_summary: internal-field exclusion -----------------------

def test_format_index_summary_default_no_data():
    assert _format_index_summary(None) == (
        '{"kospi_20d_trend": "sideways", "kospi_vs_20d_ma": "above", '
        '"kospi_2w_change_pct": 0.0, "kosdaq_20d_trend": "sideways"}'
    )


def test_format_index_summary_empty_computed_regime():
    assert _format_index_summary({"computed_regime": {}}) == (
        '{"kospi_20d_trend": "sideways", "kospi_vs_20d_ma": "above", '
        '"kospi_2w_change_pct": 0.0, "kosdaq_20d_trend": "sideways"}'
    )


def test_format_index_summary_excludes_internal_fields():
    result = _format_index_summary(SAMPLE_PREFETCHED)
    parsed = json.loads(result)
    # current/ma are internal working values — must not leak into the schema example
    assert "kospi_current" not in parsed
    assert "kospi_20d_ma" not in parsed
    assert parsed == {
        "kospi_20d_trend": "up",
        "kospi_vs_20d_ma": "above",
        "kospi_2w_change_pct": 3.5,
        "kosdaq_20d_trend": "up",
    }


# --- Sector taxonomy derivation ----------------------------------------------

def test_sector_taxonomy_falls_back_to_krx_standard_list():
    agent = create_macro_intelligence_agent(reference_date="20260101", language="ko")
    assert "IT 서비스, 건설, 금속, 기계·장비, 기타금융, 기타제조" in agent.instruction


def test_sector_taxonomy_derives_from_sector_map_ko():
    agent = create_macro_intelligence_agent(
        reference_date="20260101", language="ko", prefetched_data=SAMPLE_PREFETCHED)
    assert "## 섹터 분류 체계" in agent.instruction
    # Only the unique sectors actually present in sector_map, sorted — not the full KRX list
    assert "IT 서비스, 전기·전자" in agent.instruction
    assert "화학" not in agent.instruction


def test_sector_taxonomy_derives_from_sector_map_en():
    agent = create_macro_intelligence_agent(
        reference_date="20260101", language="en", prefetched_data=SAMPLE_PREFETCHED)
    assert "## Sector Taxonomy" in agent.instruction
    assert "IT 서비스, 전기·전자" in agent.instruction


# --- JSON output contract ----------------------------------------------------

def test_json_schema_has_required_keys_ko():
    agent = create_macro_intelligence_agent(reference_date="20260101", language="ko")
    for key in ('"analysis_date":', '"market":', '"market_regime":', '"regime_confidence":',
                '"regime_rationale":', '"simple_ma_regime":', '"index_summary":',
                '"leading_sectors":', '"lagging_sectors":', '"risk_events":',
                '"beneficiary_themes":', '"report_prose":'):
        assert key in agent.instruction, f"missing schema key: {key}"


def test_json_schema_has_required_keys_en():
    agent = create_macro_intelligence_agent(reference_date="20260101", language="en")
    for key in ('"analysis_date":', '"market":', '"market_regime":', '"regime_confidence":',
                '"regime_rationale":', '"simple_ma_regime":', '"index_summary":',
                '"leading_sectors":', '"lagging_sectors":', '"risk_events":',
                '"beneficiary_themes":', '"report_prose":'):
        assert key in agent.instruction, f"missing schema key: {key}"


def test_output_must_be_pure_json_ko():
    agent = create_macro_intelligence_agent(reference_date="20260101", language="ko")
    assert "출력은 순수 JSON만이어야 합니다" in agent.instruction
    assert "leading_sectors: 최대 5개, 신뢰도 내림차순" in agent.instruction
    assert "lagging_sectors: 최대 5개" in agent.instruction


def test_output_must_be_pure_json_en():
    agent = create_macro_intelligence_agent(reference_date="20260101", language="en")
    assert "Output MUST be pure JSON only" in agent.instruction
    assert "leading_sectors: max 5, descending confidence" in agent.instruction
    assert "lagging_sectors: max 5" in agent.instruction


# --- report_prose tone (project convention: formal Korean 합쇼체) -----------

def test_report_prose_requires_formal_korean_tone():
    agent = create_macro_intelligence_agent(reference_date="20260101", language="ko")
    assert "합쇼체를 사용하십시오: ~습니다, ~있습니다, ~됩니다" in agent.instruction


def test_report_prose_paragraph_count_guidance_ko():
    agent = create_macro_intelligence_agent(reference_date="20260101", language="ko")
    assert "3-5단락" in agent.instruction


def test_report_prose_paragraph_count_guidance_en():
    agent = create_macro_intelligence_agent(reference_date="20260101", language="en")
    assert "3-5 paragraphs" in agent.instruction
