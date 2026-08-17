"""
Rebalance scheduling for unattended (Task Scheduler-driven) runs.

Run with: python -m trading.scheduler --model six_factor --frequency quarterly --check-and-run

Meant to be invoked once a day by an external scheduler (Windows Task
Scheduler, cron, etc.) via --check-and-run: it decides for itself whether
today is a rebalance day and exits either way. There is no in-process loop --
a Python process kept alive with `while True: sleep()` has no supervisor on
Windows (doesn't restart on crash, doesn't survive reboot), so the external
scheduler's own retry/reliability semantics are used instead.

Register with, e.g.:
    schtasks /create /tn "FactorInvesting Rebalance" /sc daily /st 10:00 ^
        /tr "python -m trading.scheduler --model six_factor --frequency quarterly --check-and-run" ^
        /f
"""

import argparse
import logging
import sys
from datetime import datetime
from typing import Optional

from .alpaca_client import AlpacaClient
from .alerts import send_alert
from .strategy_trader import StrategyTrader
from data.polygon_client import PolygonClient
from config import ALPACA_PAPER

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TradingScheduler:
    """
    Decides whether a strategy is due for rebalancing and runs it if so.

    Due-date state (last rebalance time) is read back from the strategy's own
    JSONL trade log rather than kept in memory, since each --check-and-run
    invocation is a fresh process.
    """

    WEEKDAY_MAP = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 'friday': 4
    }

    def __init__(
        self,
        model_name: str,
        rebalance_frequency: str = 'quarterly',
        rebalance_day: str = 'monday',
        dry_run: bool = False
    ):
        """
        Args:
            model_name: Name of the model to run (key into main.AVAILABLE_MODELS)
            rebalance_frequency: 'weekly', 'monthly', or 'quarterly'
            rebalance_day: Day of week for weekly rebalancing
            dry_run: If True, don't execute trades
        """
        # Imported lazily to avoid a hard import-time dependency on main.py's
        # full CLI module for callers that only need AlpacaClient/StrategyTrader.
        from main import AVAILABLE_MODELS

        if model_name not in AVAILABLE_MODELS:
            raise ValueError(
                f"Unknown model: {model_name}. Available: {', '.join(AVAILABLE_MODELS.keys())}"
            )

        self.model_name = model_name
        self.model = AVAILABLE_MODELS[model_name]()
        self.rebalance_frequency = rebalance_frequency
        self.rebalance_day = rebalance_day.lower()
        self.dry_run = dry_run

        self.alpaca = AlpacaClient(paper=ALPACA_PAPER)
        self.polygon = PolygonClient()
        self.trader = StrategyTrader(
            model=self.model,
            alpaca_client=self.alpaca,
            polygon_client=self.polygon
        )

    def is_due(self, today: datetime, last_rebalance: Optional[datetime]) -> bool:
        """Check whether `today` is a rebalance day, given the last rebalance time."""
        if self.rebalance_frequency == 'weekly':
            if today.weekday() != self.WEEKDAY_MAP.get(self.rebalance_day, 0):
                return False
            return last_rebalance is None or (today - last_rebalance).days >= 3

        elif self.rebalance_frequency == 'monthly':
            if not (today.day <= 3 and today.weekday() < 5):
                return False
            return last_rebalance is None or (today - last_rebalance).days >= 20

        elif self.rebalance_frequency == 'quarterly':
            quarter_starts = [1, 4, 7, 10]
            if not (today.month in quarter_starts and today.day <= 3 and today.weekday() < 5):
                return False
            return last_rebalance is None or (today - last_rebalance).days >= 80

        return False

    def run_rebalance(self, force: bool = False):
        """Execute the rebalance. force=True skips the is_due()/drift check."""
        logger.info(f"Starting rebalance for {self.model_name} (force={force})")

        if not self.alpaca.is_market_open():
            logger.warning("Market is closed, skipping rebalance")
            return None

        result = self.trader.run_rebalance(dry_run=self.dry_run, force=force)

        if result:
            logger.info(
                f"Rebalance complete: {len(result.trades_executed)} trades, "
                f"portfolio value: ${result.portfolio_value_after:,.2f}"
            )
        else:
            logger.warning("Rebalance returned no result")

        return result

    def check_and_run(self):
        """
        Single-shot entry point for external schedulers: check is_due() against
        the persisted last-rebalance time and rebalance only if due.
        """
        today = datetime.now()
        last_rebalance = self.trader.get_last_rebalance_time()

        if not self.is_due(today, last_rebalance):
            logger.info(
                f"Not due for rebalance today ({self.rebalance_frequency}, "
                f"last rebalance: {last_rebalance})"
            )
            return None

        return self.run_rebalance(force=True)


def main():
    parser = argparse.ArgumentParser(description='Factor Investing Trading Scheduler')
    parser.add_argument('--model', '-m', required=True, help='Model name to run')
    parser.add_argument(
        '--frequency', '-f',
        choices=['weekly', 'monthly', 'quarterly'],
        default='quarterly',
        help='Rebalancing frequency'
    )
    parser.add_argument('--day', '-d', default='monday', help='Day for weekly rebalancing')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        '--check-and-run', action='store_true',
        help='Rebalance only if due today (intended for a daily external scheduler trigger)'
    )
    mode.add_argument(
        '--run-now', action='store_true',
        help='Force an immediate rebalance, ignoring the due-date check'
    )

    args = parser.parse_args()

    scheduler = TradingScheduler(
        model_name=args.model,
        rebalance_frequency=args.frequency,
        rebalance_day=args.day,
        dry_run=args.dry_run
    )

    try:
        if args.run_now:
            logger.info("Running immediate rebalance...")
            scheduler.run_rebalance(force=True)
        else:
            scheduler.check_and_run()
    except Exception as e:
        logger.error(f"Scheduled run failed: {e}")
        send_alert(
            f"{args.model}: scheduled rebalance run failed",
            f"Exception during scheduler.main() for model={args.model}, "
            f"frequency={args.frequency}: {e}"
        )
        sys.exit(1)


if __name__ == '__main__':
    main()
