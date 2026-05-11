# -*- coding: utf-8 -*-
"""
키움 증권 거래 클래스
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime

import httpx

# 임시 데이터 클래스 정의
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class Order:
    """주문 정보"""
    symbol: str
    order_type: str
    side: str
    quantity: int
    price: Optional[float]
    order_id: Optional[str]
    status: str
    account_no: Optional[str]


@dataclass
class Balance:
    """계좌 잔고 정보"""
    total_balance: float
    available_balance: float
    deposit: float
    evaluation_amount: float
    profit_loss: float
    profit_loss_rate: float


@dataclass
class Position:
    """보유 종목 정보"""
    symbol: str
    quantity: int
    average_price: float
    current_price: float
    evaluation_amount: float
    profit_loss: float
    profit_loss_rate: float


# BaseTrading 직접 정의 (임시)
class BaseTrading:
    """거래 클래스 기본 추상 클래스"""
    def __init__(self):
        pass

from .auth import KiwoomAuth

logger = logging.getLogger(__name__)


class KiwoomTrading(BaseTrading):
    """
    키움 증권 거래 클래스
    
    - 실시간 주문 처리
    - 계좌 잔고 조회
    - 보유 종목 관리
    - Rate Limiting 및 에러 핸들링
    - 실전/모의투자 모드 지원
    """

    def __init__(self, auth: KiwoomAuth, config: Optional[Dict[str, Any]] = None):
        """
        KiwoomTrading 초기화
        
        Args:
            auth: KiwoomAuth 인스턴스
            config: 추가 설정
        """
        super().__init__()
        self.auth = auth
        self.config = config or {}
        self.client = None
        self._initialized = False
        
        # Rate limiting 설정
        self.max_requests_per_second = 5  # 키움 API 제한: 초당 5회
        self._last_request_time = 0
        
        # 거래 모드 (실전/모의)
        self.trading_mode = self.config.get("trading_mode", "mock")
        
        logger.info(f"KiwoomTrading initialized with mode: {self.trading_mode}")

    async def _ensure_client(self) -> httpx.AsyncClient:
        """클라이언트가 초기화되었는지 확인하고 반환"""
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "User-Agent": "Prism-Insight/1.0",
                    "Content-Type": "application/json"
                }
            )
        return self.client

    async def _rate_limit(self):
        """Rate limiting 적용"""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < (1.0 / self.max_requests_per_second):
            wait_time = (1.0 / self.max_requests_per_second) - time_since_last
            await asyncio.sleep(wait_time)
            
        self._last_request_time = time.time()

    async def place_order(self, symbol: str, order_type: str, side: str, 
                         quantity: int, price: Optional[float] = None, 
                         account_no: Optional[str] = None) -> Dict[str, Any]:
        """
        주문을 실행합니다.
        
        Args:
            symbol: 종목코드 (예: "005930")
            order_type: 주문 유형 ("limit", "market")
            side: 매수/매도 ("buy", "sell")
            quantity: 수량
            price: 가격 (지정가 주문일 경우)
            account_no: 계좌번호 (None일 경우 기본 계좌 사용)
            
        Returns:
            주문 결과 정보
        """
        await self._rate_limit()
        
        try:
            # 토큰 가져오기
            token = await self.auth.get_token()
            
            # 거래 모드 확인
            mode = "mock" if self.trading_mode == "mock" else "real"
            
            # 주문 파라미터 구성
            order_params = {
                "symbol": symbol,
                "side": "purchase" if side == "buy" else "sell",
                "order_type": "limit" if order_type == "limit" else "market",
                "quantity": quantity,
                **({"price": price} if price is not None else {})
            }
            
            # 계좌번호 설정
            if account_no is None:
                account_no = self.auth.get_default_account()
            
            if account_no:
                order_params["account_no"] = account_no
            
            # API 호출
            url = f"{self.auth.base_url}/api/{mode}/v1/order"
            
            client = await self._ensure_client()
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json=order_params
            )
            
            response.raise_for_status()
            result = response.json()
            
            # 주문 객체 생성
            order = Order(
                symbol=symbol,
                order_type=order_type,
                side=side,
                quantity=quantity,
                price=price,
                order_id=result.get("order_no"),
                status="pending",
                account_no=account_no
            )
            
            logger.info(f"Order placed: {order}")
            return {"success": True, "order": order, "raw_response": result}
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during order placement: {e}")
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
                "order": None
            }
        except Exception as e:
            logger.error(f"Error during order placement: {e}")
            return {"success": False, "error": str(e), "order": None}

    async def cancel_order(self, order_id: str, account_no: Optional[str] = None) -> Dict[str, Any]:
        """
        주문을 취소합니다.
        
        Args:
            order_id: 취소할 주문 ID
            account_no: 계좌번호
            
        Returns:
            취소 결과
        """
        await self._rate_limit()
        
        try:
            token = await self.auth.get_token()
            mode = "mock" if self.trading_mode == "mock" else "real"
            
            if account_no is None:
                account_no = self.auth.get_default_account()
            
            url = f"{self.auth.base_url}/api/{mode}/v1/order/{order_id}/cancel"
            
            client = await self._ensure_client()
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json={"account_no": account_no} if account_no else {}
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Order cancelled: {order_id}")
            return {"success": True, "raw_response": result}
            
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return {"success": False, "error": str(e)}

    async def get_balance(self, account_no: Optional[str] = None) -> Balance:
        """
        계좌 잔고를 조회합니다.
        
        Args:
            account_no: 계좌번호
            
        Returns:
            계좌 잔고 정보
        """
        await self._rate_limit()
        
        try:
            token = await self.auth.get_token()
            mode = "mock" if self.trading_mode == "mock" else "real"
            
            if account_no is None:
                account_no = self.auth.get_default_account()
            
            url = f"{self.auth.base_url}/api/{mode}/v1/account/balance"
            params = {"account_no": account_no} if account_no else {}
            
            client = await self._ensure_client()
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                params=params
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Balance 객체 생성
            balance = Balance(
                total_balance=float(data.get("total_balance", 0)),
                available_balance=float(data.get("available_balance", 0)),
                deposit=float(data.get("deposit", 0)),
                evaluation_amount=float(data.get("evaluation_amount", 0)),
                profit_loss=float(data.get("profit_loss", 0)),
                profit_loss_rate=float(data.get("profit_loss_rate", 0))
            )
            
            logger.debug(f"Balance retrieved: {balance}")
            return balance
            
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            # 에러 발생 시 기본값 반환
            return Balance(0, 0, 0, 0, 0, 0)

    async def get_positions(self, account_no: Optional[str] = None) -> List[Position]:
        """
        보유 종목을 조회합니다.
        
        Args:
            account_no: 계좌번호
            
        Returns:
            보유 종목 리스트
        """
        await self._rate_limit()
        
        try:
            token = await self.auth.get_token()
            mode = "mock" if self.trading_mode == "mock" else "real"
            
            if account_no is None:
                account_no = self.auth.get_default_account()
            
            url = f"{self.auth.base_url}/api/{mode}/v1/account/positions"
            params = {"account_no": account_no} if account_no else {}
            
            client = await self._ensure_client()
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                params=params
            )
            
            response.raise_for_status()
            data = response.json()
            
            positions = []
            for item in data.get("positions", []):
                position = Position(
                    symbol=item.get("symbol", ""),
                    quantity=int(item.get("quantity", 0)),
                    average_price=float(item.get("average_price", 0)),
                    current_price=float(item.get("current_price", 0)),
                    evaluation_amount=float(item.get("evaluation_amount", 0)),
                    profit_loss=float(item.get("profit_loss", 0)),
                    profit_loss_rate=float(item.get("profit_loss_rate", 0))
                )
                positions.append(position)
            
            logger.debug(f"Positions retrieved: {len(positions)} items")
            return positions
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    async def get_order_status(self, order_id: str, account_no: Optional[str] = None) -> Dict[str, Any]:
        """
        주문 상태를 조회합니다.
        
        Args:
            order_id: 주문 ID
            account_no: 계좌번호
            
        Returns:
            주문 상태 정보
        """
        await self._rate_limit()
        
        try:
            token = await self.auth.get_token()
            mode = "mock" if self.trading_mode == "mock" else "real"
            
            if account_no is None:
                account_no = self.auth.get_default_account()
            
            url = f"{self.auth.base_url}/api/{mode}/v1/order/{order_id}"
            params = {"account_no": account_no} if account_no else {}
            
            client = await self._ensure_client()
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                params=params
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Order 객체 생성
            order_data = data.get("order", {})
            order = Order(
                symbol=order_data.get("symbol", ""),
                order_type=order_data.get("order_type", ""),
                side=order_data.get("side", ""),
                quantity=int(order_data.get("quantity", 0)),
                price=float(order_data.get("price", 0)) if order_data.get("price") else None,
                order_id=order_id,
                status=order_data.get("status", "unknown"),
                account_no=account_no
            )
            
            return {"success": True, "order": order, "raw_response": data}
            
        except Exception as e:
            logger.error(f"Error getting order status {order_id}: {e}")
            return {"success": False, "error": str(e), "order": None}

    async def get_order_history(self, start_date: Optional[str] = None,
                               end_date: Optional[str] = None,
                               account_no: Optional[str] = None) -> List[Order]:
        """
        주문 내역을 조회합니다.
        
        Args:
            start_date: 시작 날짜 (YYYY-MM-DD)
            end_date: 종료 날짜 (YYYY-MM-DD)
            account_no: 계좌번호
            
        Returns:
            주문 내역 리스트
        """
        await self._rate_limit()
        
        try:
            token = await self.auth.get_token()
            mode = "mock" if self.trading_mode == "mock" else "real"
            
            if account_no is None:
                account_no = self.auth.get_default_account()
            
            url = f"{self.auth.base_url}/api/{mode}/v1/account/orders"
            params = {"account_no": account_no} if account_no else {}
            
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date
            
            client = await self._ensure_client()
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                params=params
            )
            
            response.raise_for_status()
            data = response.json()
            
            orders = []
            for item in data.get("orders", []):
                order = Order(
                    symbol=item.get("symbol", ""),
                    order_type=item.get("order_type", ""),
                    side=item.get("side", ""),
                    quantity=int(item.get("quantity", 0)),
                    price=float(item.get("price", 0)) if item.get("price") else None,
                    order_id=item.get("order_no"),
                    status=item.get("status", "unknown"),
                    account_no=account_no
                )
                orders.append(order)
            
            logger.debug(f"Order history retrieved: {len(orders)} orders")
            return orders
            
        except Exception as e:
            logger.error(f"Error getting order history: {e}")
            return []

    async def close(self):
        """리소스 정리"""
        if self.client:
            await self.client.aclose()
            self.client = None
            logger.info("KiwoomTrading client closed")

    def __del__(self):
        """소멸자에서 리소스 정리"""
        if self.client and hasattr(self.client, "aclose"):
            try:
                asyncio.create_task(self.close())
            except:
                pass