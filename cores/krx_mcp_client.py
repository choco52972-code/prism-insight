"""
KRX MCP Client

krx_data_client 모듈과 동일한 공개 API를 제공하되,
kospi-kosdaq-stock-server MCP 서버를 경유하여 데이터를 조회합니다.

사용법:
    from cores.krx_mcp_client import (
        get_market_ohlcv_by_date,
        get_nearest_business_day_in_a_week,
        get_market_ohlcv_by_ticker,
        ...
    )
"""
import asyncio
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

_PRISM_ROOT = Path(__file__).parent.parent
_CONFIG_PATH = _PRISM_ROOT / "mcp_agent.config.yaml"


def _load_server_config() -> dict:
    """mcp_agent.config.yaml에서 kospi_kosdaq 서버 설정을 읽습니다."""
    try:
        import yaml
        with open(_CONFIG_PATH) as f:
            config = yaml.safe_load(f)
        srv = config["mcp"]["servers"]["kospi_kosdaq"]
        server_env = {**os.environ, **srv.get("env", {})}
        return {
            "command": srv.get("command", "python3"),
            "args": srv.get("args", []),
            "env": server_env,
        }
    except Exception as e:
        logger.warning(f"mcp_agent.config.yaml 읽기 실패, 환경변수 사용: {e}")
        return {
            "command": "/home/leedw/projects/prism-insight/venv/bin/python3",
            "args": ["/home/leedw/projects/kospi-kosdaq-stock-server/kospi_kosdaq_stock_server.py"],
            "env": {
                **os.environ,
                "KRX_ID": os.environ.get("KRX_ID", ""),
                "KRX_PW": os.environ.get("KRX_PW", ""),
                "KRX_LOGIN_METHOD": os.environ.get("KRX_LOGIN_METHOD", "krx"),
                "PYTHONPATH": "/home/leedw/projects/kospi-kosdaq-stock-server",
            },
        }


def _parse_tool_result(result: Any) -> Any:
    """MCP CallToolResult에서 Python 값을 추출합니다."""
    if getattr(result, "isError", False):
        error_text = " ".join(
            getattr(block, "text", str(block)) for block in (result.content or [])
        )
        raise RuntimeError(f"MCP tool error: {error_text}")
    for block in result.content or []:
        text = getattr(block, "text", None)
        if text is not None:
            try:
                return json.loads(text)
            except (json.JSONDecodeError, TypeError):
                return text
    return {}


def _to_date_df(data: Any) -> pd.DataFrame:
    """날짜 키 딕셔너리를 DatetimeIndex DataFrame으로 변환합니다."""
    if not isinstance(data, dict) or not data:
        return pd.DataFrame()
    if "error" in data:
        logger.warning(f"KRX MCP 서버 오류: {data['error']}")
        return pd.DataFrame()
    df = pd.DataFrame.from_dict(data, orient="index")
    df.index = pd.to_datetime(df.index)
    df.index.name = "날짜"
    return df.sort_index()


def _to_ticker_df(data: Any) -> pd.DataFrame:
    """티커 키 딕셔너리를 DataFrame으로 변환합니다 (인덱스 = 티커 코드)."""
    if not isinstance(data, dict) or not data:
        return pd.DataFrame()
    if "error" in data:
        logger.warning(f"KRX MCP 서버 오류: {data['error']}")
        return pd.DataFrame()
    df = pd.DataFrame.from_dict(data, orient="index")
    df.index.name = "Ticker"
    return df


class _MCPClientManager:
    """백그라운드 스레드에서 MCP 서버 프로세스와의 영구 연결을 관리합니다."""

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._session: Any = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._init_error: Optional[Exception] = None
        self._start_lock = threading.Lock()
        self._started = False
        self._stdio_cm: Any = None
        self._session_cm: Any = None

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect())
        except Exception as exc:
            self._init_error = exc
            self._ready.set()
            return
        self._loop.run_forever()

    async def _connect(self) -> None:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        cfg = _load_server_config()
        params = StdioServerParameters(
            command=cfg["command"],
            args=cfg["args"],
            env=cfg["env"],
        )
        self._stdio_cm = stdio_client(params)
        read, write = await self._stdio_cm.__aenter__()
        self._session_cm = ClientSession(read, write)
        self._session = await self._session_cm.__aenter__()
        await self._session.initialize()
        logger.info("KRX MCP 클라이언트 연결 완료")
        self._ready.set()

    def ensure_started(self) -> None:
        with self._start_lock:
            if self._started:
                return
            self._started = True
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
        self._ready.wait(timeout=60)
        if self._init_error:
            raise RuntimeError(
                f"KRX MCP 클라이언트 시작 실패: {self._init_error}"
            ) from self._init_error
        if not self._ready.is_set():
            raise RuntimeError("KRX MCP 클라이언트 60초 내 응답 없음")

    def call_tool(self, name: str, args: dict) -> Any:
        """동기 tool 호출 — 어느 컨텍스트에서나 안전."""
        self.ensure_started()
        future = asyncio.run_coroutine_threadsafe(
            self._session.call_tool(name, args), self._loop
        )
        try:
            return _parse_tool_result(future.result(timeout=300))
        except TimeoutError as exc:
            raise RuntimeError(f"KRX MCP tool '{name}' timed out (300s)") from exc

    async def call_tool_async(self, name: str, args: dict) -> Any:
        """비동기 tool 호출 — async 함수 내부에서 사용."""
        self.ensure_started()
        future = asyncio.run_coroutine_threadsafe(
            self._session.call_tool(name, args), self._loop
        )
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(None, lambda: future.result(timeout=300))
        except TimeoutError as exc:
            raise RuntimeError(f"KRX MCP tool '{name}' timed out (300s)") from exc
        return _parse_tool_result(result)


_manager = _MCPClientManager()


# ---------------------------------------------------------------------------
# 공개 API — krx_data_client 모듈 수준 함수와 동일한 시그니처
# ---------------------------------------------------------------------------

def get_market_ohlcv_by_date(
    fromdate: str, todate: str, ticker: str, adjusted: bool = True
) -> pd.DataFrame:
    data = _manager.call_tool(
        "get_stock_ohlcv",
        {"fromdate": fromdate, "todate": todate, "ticker": ticker, "adjusted": adjusted},
    )
    return _to_date_df(data)


async def async_get_market_ohlcv_by_date(
    fromdate: str, todate: str, ticker: str, adjusted: bool = True
) -> pd.DataFrame:
    data = await _manager.call_tool_async(
        "get_stock_ohlcv",
        {"fromdate": fromdate, "todate": todate, "ticker": ticker, "adjusted": adjusted},
    )
    return _to_date_df(data)


def get_market_ohlcv_by_ticker(date: str, market: str = "ALL") -> pd.DataFrame:
    data = _manager.call_tool("get_all_stocks_ohlcv", {"date": date, "market": market})
    return _to_ticker_df(data)


def get_market_cap_by_date(fromdate: str, todate: str, ticker: str) -> pd.DataFrame:
    data = _manager.call_tool(
        "get_stock_market_cap",
        {"fromdate": fromdate, "todate": todate, "ticker": ticker},
    )
    return _to_date_df(data)


def get_market_cap_by_ticker(date: str, market: str = "ALL") -> pd.DataFrame:
    data = _manager.call_tool("get_all_stocks_market_cap", {"date": date, "market": market})
    return _to_ticker_df(data)


def get_market_fundamental_by_date(fromdate: str, todate: str, ticker: str) -> pd.DataFrame:
    data = _manager.call_tool(
        "get_stock_fundamental",
        {"fromdate": fromdate, "todate": todate, "ticker": ticker},
    )
    return _to_date_df(data)


def get_market_trading_volume_by_date(
    fromdate: str, todate: str, ticker: str, detail: bool = False
) -> pd.DataFrame:
    data = _manager.call_tool(
        "get_stock_trading_volume",
        {"fromdate": fromdate, "todate": todate, "ticker": ticker, "detail": detail},
    )
    return _to_date_df(data)


def get_market_trading_volume_by_investor(
    fromdate: str, todate: str, ticker: str, detail: bool = False
) -> pd.DataFrame:
    return get_market_trading_volume_by_date(fromdate, todate, ticker, detail=detail)


def get_market_trading_value_by_date(
    fromdate: str, todate: str, ticker: str, on: str = "순매수"
) -> pd.DataFrame:
    data = _manager.call_tool(
        "get_stock_trading_value",
        {"fromdate": fromdate, "todate": todate, "ticker": ticker, "on": on},
    )
    return _to_date_df(data)


def get_market_trading_value_by_investor(
    fromdate: str, todate: str, ticker: str, detail: bool = False
) -> pd.DataFrame:
    data = _manager.call_tool(
        "get_stock_trading_value",
        {"fromdate": fromdate, "todate": todate, "ticker": ticker},
    )
    return _to_date_df(data)


def get_index_ohlcv_by_date(
    fromdate: str, todate: str, ticker: str, freq: str = "d"
) -> pd.DataFrame:
    data = _manager.call_tool(
        "get_index_ohlcv",
        {"fromdate": fromdate, "todate": todate, "ticker": ticker, "freq": freq},
    )
    return _to_date_df(data)


async def async_get_index_ohlcv_by_date(
    fromdate: str, todate: str, ticker: str, freq: str = "d"
) -> pd.DataFrame:
    data = await _manager.call_tool_async(
        "get_index_ohlcv",
        {"fromdate": fromdate, "todate": todate, "ticker": ticker, "freq": freq},
    )
    return _to_date_df(data)


def get_market_ticker_name(ticker: str) -> str:
    data = _manager.call_tool("get_ticker_name", {"ticker": ticker})
    if isinstance(data, dict):
        return data.get("name", "")
    return str(data) if data else ""


def get_nearest_business_day_in_a_week(
    target_date: Optional[str] = None, prev: bool = True
) -> str:
    args: Dict[str, Any] = {"prev": prev}
    if target_date:
        args["target_date"] = target_date
    data = _manager.call_tool("get_nearest_business_day", args)
    if isinstance(data, dict):
        return data.get("date", target_date or "")
    return str(data) if data else (target_date or "")


def load_all_tickers() -> Dict[str, str]:
    """전체 종목 코드-이름 매핑 반환 (update_stock_data.py 용)."""
    data = _manager.call_tool("load_all_tickers", {})
    if isinstance(data, dict) and "error" not in data:
        return data
    return {}
