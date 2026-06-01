"""
KIS 모의계좌 잔고조회 / 매수 / 매도 테스트

실행 방법:
    cd /home/leedw/projects/prism-insight
    python tests/test_kis_order.py

주의:
    - 반드시 demo(모의) 모드에서만 실행됩니다.
    - 매수/매도는 메뉴에서 명시적으로 선택해야 실행됩니다.
    - 테스트 종목: 삼성전자(005930) 기본값, 실행 시 변경 가능
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from trading.domestic_stock_trading import AsyncTradingContext

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

BUY_AMOUNT = 10_000  # 테스트 매수 금액 (원)
DEFAULT_STOCK = "005930"  # 삼성전자


# ──────────────────────────────────────────────
# 1. 잔고 조회
# ──────────────────────────────────────────────
async def show_balance():
    print("\n" + "=" * 50)
    print("📊 잔고 조회")
    print("=" * 50)

    async with AsyncTradingContext("demo", BUY_AMOUNT) as trader:
        balance = await trader.get_balance()
        positions = await trader.get_positions()

    print(f"  예수금      : {balance.deposit:>15,.0f} 원")
    print(f"  총평가금액  : {balance.total_balance:>15,.0f} 원")
    print(f"  총손익      : {balance.profit_loss:>+15,.0f} 원")
    print(f"  총수익률    : {balance.profit_loss_rate:>+14.2f} %")
    print(f"  주문가능현금: {balance.available_balance:>15,.0f} 원")

    print(f"\n  보유종목 ({len(positions)}개):")
    if positions:
        for p in positions:
            print(
                f"    {p.symbol}  {p.quantity}주  "
                f"평균 {p.average_price:,.0f}원  "
                f"현재 {p.current_price:,.0f}원  "
                f"손익 {p.profit_loss_rate:+.2f}%"
            )
    else:
        print("    보유 종목 없음")

    return positions, balance


# ──────────────────────────────────────────────
# 2. 현재가 조회
# ──────────────────────────────────────────────
async def show_price(stock_code: str):
    print(f"\n현재가 조회: {stock_code}")
    async with AsyncTradingContext("demo", BUY_AMOUNT) as trader:
        price = await trader.get_current_price(stock_code)

    print(f"  → {stock_code} 현재가: {int(price.current_price):,} 원  ({price.change_rate:+.2f}%)")
    return price


# ──────────────────────────────────────────────
# 3. 매수 주문
# ──────────────────────────────────────────────
async def do_buy(stock_code: str):
    print(f"\n" + "=" * 50)
    print(f"🛒 매수 주문: {stock_code}  (모의, {BUY_AMOUNT:,}원)")
    print("=" * 50)

    async with AsyncTradingContext("demo", BUY_AMOUNT) as trader:
        result = await trader.async_buy_stock(stock_code, timeout=30.0)

    if result.get("success"):
        print(f"  ✅ 매수 성공: {result.get('message')}")
    else:
        print(f"  ❌ 매수 실패: {result.get('message')}")
    return result


# ──────────────────────────────────────────────
# 4. 매도 주문
# ──────────────────────────────────────────────
async def do_sell(stock_code: str):
    print(f"\n" + "=" * 50)
    print(f"💸 매도 주문: {stock_code}  (모의, 전량)")
    print("=" * 50)

    async with AsyncTradingContext("demo", BUY_AMOUNT) as trader:
        result = await trader.async_sell_stock(stock_code, timeout=30.0)

    if result.get("success"):
        print(f"  ✅ 매도 성공: {result.get('message')}")
    else:
        print(f"  ❌ 매도 실패: {result.get('message')}")
    return result


# ──────────────────────────────────────────────
# 메인 메뉴
# ──────────────────────────────────────────────
async def main():
    print("=" * 50)
    print("🧪 KIS 모의계좌 테스트 (demo 전용)")
    print("=" * 50)

    stock_code = input(f"\n테스트 종목 코드 (Enter = {DEFAULT_STOCK} 삼성전자): ").strip()
    if not stock_code:
        stock_code = DEFAULT_STOCK

    while True:
        print(f"\n[종목: {stock_code}]")
        print("  1. 잔고/포트폴리오 조회")
        print("  2. 현재가 조회")
        print("  3. 매수 주문")
        print("  4. 매도 주문")
        print("  5. 종목 변경")
        print("  0. 종료")

        choice = input("\n선택: ").strip()

        if choice == "1":
            await show_balance()
        elif choice == "2":
            await show_price(stock_code)
        elif choice == "3":
            confirm = input(f"  {stock_code} 모의 매수를 실행합니까? (y/N): ").strip().lower()
            if confirm == "y":
                await do_buy(stock_code)
            else:
                print("  취소됨")
        elif choice == "4":
            confirm = input(f"  {stock_code} 모의 매도를 실행합니까? (y/N): ").strip().lower()
            if confirm == "y":
                await do_sell(stock_code)
            else:
                print("  취소됨")
        elif choice == "5":
            stock_code = input("  새 종목 코드: ").strip() or stock_code
        elif choice == "0":
            print("\n종료합니다.")
            break
        else:
            print("  올바른 번호를 입력하세요.")


if __name__ == "__main__":
    asyncio.run(main())
