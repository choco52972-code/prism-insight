#!/usr/bin/env python3
"""
Stock information update script

Run periodically to update stock information (codes, names) daily
"""
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

import os
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path

from cores.krx_mcp_client import load_all_tickers

# Logging configuration
_LOGS_DIR = Path(__file__).parent / "logs"
_LOGS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(_LOGS_DIR / "stock_data_update.log")
    ]
)
logger = logging.getLogger(__name__)

def update_stock_data(output_file="stock_map.json"):
    """
    Update stock information

    Args:
        output_file (str): File path to save

    Returns:
        bool: Success status
    """
    try:
        # Today's date
        today = datetime.now().strftime("%Y%m%d")
        logger.info(f"Starting stock data update: {today}")

        # Fetch all stock code-name mappings at once (efficient!)
        logger.info("Fetching all stock information...")
        code_to_name = load_all_tickers()
        logger.info(f"Loaded {len(code_to_name)} stocks")

        # Create reverse mapping
        name_to_code = {name: code for code, name in code_to_name.items()}

        # Save data
        data = {
            "code_to_name": code_to_name,
            "name_to_code": name_to_code,
            "updated_at": datetime.now().isoformat()
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Stock data update complete: {len(code_to_name)} stocks, file: {output_file}")
        return True
    except Exception as e:
        logger.error(f"Stock data update failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    parser = argparse.ArgumentParser(description="Update stock information")
    parser.add_argument("--output", default="stock_map.json", help="File path to save")

    args = parser.parse_args()
    update_stock_data(args.output)

if __name__ == "__main__":
    main()