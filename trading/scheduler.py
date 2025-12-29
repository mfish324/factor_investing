"""
Scheduler for automated rebalancing.

Run with: python -m trading.scheduler --model six_factor
"""

import argparse
import logging
import time
from datetime import datetime, timedelta
from typing import Optional
import schedule

from .alpaca_client import AlpacaClient
from .strategy_trader import StrategyTrader
from data.polygon_client import PolygonClient
from models.magic_formula import MagicFormulaModel
from models.piotroski import PiotroskiModel
from models.garp import GARPModel
from models.quality_value import QualityValueModel
from models.three_factor import ThreeFactorModel
from models.six_factor import SixFactorModel

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

AVAILABLE_MODELS = {
    'magic_formula': MagicFormulaModel,
    'piotroski': PiotroskiModel,
    'garp': GARPModel,
    'quality_value': QualityValueModel,
    'three_factor': ThreeFactorModel,
    'six_factor': SixFactorModel,
}


class TradingScheduler:
    """
    Scheduler for automated portfolio rebalancing.

    Supports:
    - Weekly, monthly, or quarterly rebalancing
    - Automatic retry on failure
    - Email notifications (optional)
    """

    def __init__(
        self,
        model_name: str,
        rebalance_frequency: str = 'quarterly',
        rebalance_day: str = 'monday',
        rebalance_time: str = '10:00',
        dry_run: bool = False
    ):
        """
        Initialize scheduler.

        Args:
            model_name: Name of the model to run
            rebalance_frequency: 'weekly', 'monthly', or 'quarterly'
            rebalance_day: Day of week for weekly rebalancing
            rebalance_time: Time to run rebalance (HH:MM)
            dry_run: If True, don't execute trades
        """
        if model_name not in AVAILABLE_MODELS:
            raise ValueError(f"Unknown model: {model_name}")

        self.model_name = model_name
        self.model = AVAILABLE_MODELS[model_name]()
        self.rebalance_frequency = rebalance_frequency
        self.rebalance_day = rebalance_day.lower()
        self.rebalance_time = rebalance_time
        self.dry_run = dry_run

        self.alpaca = AlpacaClient(paper=True)
        self.polygon = PolygonClient()
        self.trader = StrategyTrader(
            model=self.model,
            alpaca_client=self.alpaca,
            polygon_client=self.polygon
        )

        self.last_rebalance: Optional[datetime] = None
        self.next_rebalance: Optional[datetime] = None

    def should_rebalance_today(self) -> bool:
        """Check if today is a rebalance day based on frequency."""
        today = datetime.now()

        if self.rebalance_frequency == 'weekly':
            # Rebalance on specified day of week
            day_map = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2,
                'thursday': 3, 'friday': 4
            }
            return today.weekday() == day_map.get(self.rebalance_day, 0)

        elif self.rebalance_frequency == 'monthly':
            # Rebalance on first trading day of month
            # (simplified: just check if it's the first weekday)
            return today.day <= 3 and today.weekday() < 5

        elif self.rebalance_frequency == 'quarterly':
            # Rebalance on first trading day of quarter
            quarter_starts = [1, 4, 7, 10]
            return today.month in quarter_starts and today.day <= 3 and today.weekday() < 5

        return False

    def run_rebalance(self):
        """Execute the rebalance."""
        logger.info(f"Starting scheduled rebalance for {self.model_name}")

        try:
            # Check if market is open
            if not self.alpaca.is_market_open():
                logger.warning("Market is closed, skipping rebalance")
                return

            # Run the rebalance
            result = self.trader.run_rebalance(
                dry_run=self.dry_run,
                force=True  # Always rebalance on scheduled day
            )

            if result:
                self.last_rebalance = datetime.now()
                logger.info(
                    f"Rebalance complete: {len(result.trades_executed)} trades, "
                    f"portfolio value: ${result.portfolio_value_after:,.2f}"
                )
            else:
                logger.warning("Rebalance returned no result")

        except Exception as e:
            logger.error(f"Rebalance failed: {e}")

    def start(self):
        """Start the scheduler."""
        logger.info(f"Starting trading scheduler for {self.model_name}")
        logger.info(f"Frequency: {self.rebalance_frequency}")
        logger.info(f"Time: {self.rebalance_time}")
        logger.info(f"Dry run: {self.dry_run}")

        # Schedule based on frequency
        if self.rebalance_frequency == 'weekly':
            day_method = getattr(schedule.every(), self.rebalance_day)
            day_method.at(self.rebalance_time).do(self.run_rebalance)

        elif self.rebalance_frequency == 'monthly':
            # Check daily at the specified time
            schedule.every().day.at(self.rebalance_time).do(self._check_and_rebalance_monthly)

        elif self.rebalance_frequency == 'quarterly':
            # Check daily at the specified time
            schedule.every().day.at(self.rebalance_time).do(self._check_and_rebalance_quarterly)

        else:
            # Default: check daily
            schedule.every().day.at(self.rebalance_time).do(self.run_rebalance)

        # Print next scheduled run
        jobs = schedule.get_jobs()
        if jobs:
            logger.info(f"Next run: {jobs[0].next_run}")

        # Run the scheduler loop
        logger.info("Scheduler running. Press Ctrl+C to stop.")
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("Scheduler stopped")

    def _check_and_rebalance_monthly(self):
        """Check if it's the first trading day of the month."""
        today = datetime.now()
        if today.day <= 3 and today.weekday() < 5:
            # Avoid rebalancing multiple times in the same period
            if self.last_rebalance and (today - self.last_rebalance).days < 20:
                logger.info("Already rebalanced this month, skipping")
                return
            self.run_rebalance()

    def _check_and_rebalance_quarterly(self):
        """Check if it's the first trading day of the quarter."""
        today = datetime.now()
        quarter_starts = [1, 4, 7, 10]
        if today.month in quarter_starts and today.day <= 3 and today.weekday() < 5:
            # Avoid rebalancing multiple times in the same period
            if self.last_rebalance and (today - self.last_rebalance).days < 80:
                logger.info("Already rebalanced this quarter, skipping")
                return
            self.run_rebalance()


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
    parser.add_argument('--time', '-t', default='10:00', help='Time to run (HH:MM)')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode')
    parser.add_argument('--run-now', action='store_true', help='Run rebalance immediately')

    args = parser.parse_args()

    scheduler = TradingScheduler(
        model_name=args.model,
        rebalance_frequency=args.frequency,
        rebalance_day=args.day,
        rebalance_time=args.time,
        dry_run=args.dry_run
    )

    if args.run_now:
        logger.info("Running immediate rebalance...")
        scheduler.run_rebalance()
    else:
        scheduler.start()


if __name__ == '__main__':
    main()
