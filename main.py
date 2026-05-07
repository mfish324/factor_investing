#!/usr/bin/env python3
"""
Factor Investing Analysis Application - CLI Entry Point

Usage:
    python main.py run --all          # Run all models
    python main.py run --model magic_formula
    python main.py compare            # Compare model results
    python main.py report --output results/
    python main.py update-data        # Update data cache
    python main.py list-models        # List available models
    python main.py train-ml           # Train ML models
"""

import click
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd

from config import (
    POLYGON_API_KEY,
    BACKTEST_START_DATE,
    BACKTEST_END_DATE,
    DEFAULT_PORTFOLIO_SIZE,
    DEFAULT_REBALANCE_FREQUENCY,
    RESULTS_DIR,
    ROTATION_DEFAULT_METHOD,
    ROTATION_REBALANCE_FREQ,
    ML_TRAINING_START,
    MODELS_DIR,
)
from data.polygon_client import PolygonClient
from data.cache import CacheManager
from data.universe import UniverseManager
from models.magic_formula import MagicFormulaModel
from models.piotroski import PiotroskiModel
from models.garp import GARPModel
from models.quality_value import QualityValueModel
from models.three_factor import ThreeFactorModel
from models.six_factor import SixFactorModel
from models.low_volatility import LowVolatilityModel
from models.shareholder_yield import ShareholderYieldModel
from models.ml_ensemble import MLEnsembleModel
from backtesting.engine import BacktestEngine, run_multiple_backtests
from backtesting.metrics import BacktestResult
from analysis.comparison import ModelComparison
from analysis.visualization import FactorVisualizer

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Available models registry
AVAILABLE_MODELS = {
    'magic_formula': MagicFormulaModel,
    'piotroski': PiotroskiModel,
    'garp': GARPModel,
    'quality_value': QualityValueModel,
    'three_factor': ThreeFactorModel,
    'six_factor': SixFactorModel,
    'low_volatility': LowVolatilityModel,
    'shareholder_yield': ShareholderYieldModel,
    'ml_ensemble': lambda: MLEnsembleModel(model_path=str(MODELS_DIR / 'ml_ensemble.joblib')),
}


def get_polygon_client() -> PolygonClient:
    """Get Polygon client with API key validation."""
    if not POLYGON_API_KEY:
        logger.error("POLYGON_API_KEY environment variable not set")
        logger.info("Set it with: export POLYGON_API_KEY='your_key_here'")
        sys.exit(1)
    return PolygonClient()


def load_data(
    polygon_client: PolygonClient,
    universe: List[str],
    start_date: str,
    end_date: str,
    show_progress: bool = True
) -> tuple:
    """
    Load financial and price data for the universe.

    Returns:
        Tuple of (financials_dict, prices_dict, market_caps, benchmark_prices)
    """
    from tqdm import tqdm

    logger.info(f"Loading data for {len(universe)} stocks...")

    # Load financials
    financials = {}
    iterator = tqdm(universe, desc="Loading financials") if show_progress else universe
    for ticker in iterator:
        try:
            df = polygon_client.get_financials(ticker, period='annual')
            if not df.empty:
                financials[ticker] = df
        except Exception as e:
            logger.warning(f"Failed to load financials for {ticker}: {e}")

    # Load prices, truncated to end_date (cache may extend past it; preventing
    # that leakage is what makes results reproducible across runs).
    end_ts = pd.Timestamp(end_date)
    prices = {}
    iterator = tqdm(universe, desc="Loading prices") if show_progress else universe
    for ticker in iterator:
        try:
            df = polygon_client.get_prices(ticker, start_date, end_date)
            if df.empty:
                continue
            if 'date' in df.columns:
                df = df[pd.to_datetime(df['date']) <= end_ts]
            else:
                df = df.loc[df.index <= end_ts]
            if not df.empty:
                prices[ticker] = df
        except Exception as e:
            logger.warning(f"Failed to load prices for {ticker}: {e}")

    # Get market caps. Polygon returns *today's* snapshot, so we also derive an
    # implied shares_outstanding (mc / latest_cached_price). The engine uses
    # shares to compute mc as-of each rebalance date, removing look-ahead bias
    # from market-cap-derived signals (P/E, EV/EBITDA, etc.).
    market_caps = {}
    shares_outstanding = {}
    iterator = tqdm(universe, desc="Loading market caps") if show_progress else universe
    for ticker in iterator:
        try:
            mc = polygon_client.get_market_cap(ticker)
            if not mc:
                continue
            market_caps[ticker] = mc
            df = prices.get(ticker)
            if df is None or df.empty or 'close' not in df.columns:
                continue
            latest_price = df.iloc[-1]['close']
            if latest_price and latest_price > 0:
                shares_outstanding[ticker] = mc / float(latest_price)
        except Exception as e:
            pass

    # Load benchmark (SPY), also truncated to end_date
    benchmark_prices = None
    try:
        benchmark_prices = polygon_client.get_prices('SPY', start_date, end_date)
        if benchmark_prices is not None and not benchmark_prices.empty:
            if 'date' in benchmark_prices.columns:
                benchmark_prices = benchmark_prices[
                    pd.to_datetime(benchmark_prices['date']) <= end_ts
                ]
            else:
                benchmark_prices = benchmark_prices.loc[benchmark_prices.index <= end_ts]
    except Exception as e:
        logger.warning(f"Failed to load benchmark prices: {e}")

    logger.info(f"Loaded: {len(financials)} financials, {len(prices)} prices, {len(market_caps)} market caps")

    return financials, prices, market_caps, benchmark_prices, shares_outstanding


@click.group()
def cli():
    """Factor Investing Analysis Application"""
    pass


@cli.command()
@click.option('--all', 'run_all', is_flag=True, help='Run all available models')
@click.option('--model', '-m', multiple=True, help='Specific model(s) to run')
@click.option('--start-date', default=BACKTEST_START_DATE, help='Backtest start date')
@click.option('--end-date', default=BACKTEST_END_DATE, help='Backtest end date')
@click.option('--portfolio-size', default=DEFAULT_PORTFOLIO_SIZE, help='Number of stocks')
@click.option('--rebalance', default=DEFAULT_REBALANCE_FREQUENCY, help='Rebalance frequency')
@click.option('--output', '-o', default=None, help='Output directory')
@click.option('--no-pit-membership', is_flag=True, help='Disable point-in-time S&P 500 membership filter (forces survivorship-biased current snapshot)')
def run(run_all, model, start_date, end_date, portfolio_size, rebalance, output, no_pit_membership):
    """Run backtests for factor models."""

    # Determine which models to run
    if run_all:
        models_to_run = list(AVAILABLE_MODELS.keys())
    elif model:
        models_to_run = list(model)
    else:
        click.echo("Please specify --all or --model <name>")
        click.echo("Available models: " + ", ".join(AVAILABLE_MODELS.keys()))
        return

    # Validate models
    for m in models_to_run:
        if m not in AVAILABLE_MODELS:
            click.echo(f"Unknown model: {m}")
            click.echo("Available models: " + ", ".join(AVAILABLE_MODELS.keys()))
            return

    click.echo(f"Running models: {', '.join(models_to_run)}")
    click.echo(f"Period: {start_date} to {end_date}")

    # Initialize clients
    polygon_client = get_polygon_client()
    universe_manager = UniverseManager()

    # Membership: prefer historical (PIT) when available; fall back to current
    # snapshot otherwise. Pass-through to engine so it filters per rebalance.
    membership_db = None
    if not no_pit_membership:
        try:
            from data.sp500_membership import MembershipDB
            membership_db = MembershipDB()
            membership_db.status()  # raises softly if empty
            universe = universe_manager.get_universe_union(
                start_date, end_date, exclude_financials=True
            )
            click.echo(
                f"Universe (point-in-time): {len(universe)} tickers across "
                f"{start_date} to {end_date}"
            )
        except Exception as e:
            click.echo(
                f"Falling back to current S&P 500 snapshot ({e}). "
                f"Run `shadow build-membership` first to enable PIT mode."
            )
            membership_db = None
            universe = universe_manager.get_universe('sp500', exclude_financials=True)
            click.echo(f"Universe (current snapshot): {len(universe)} stocks")
    else:
        universe = universe_manager.get_universe('sp500', exclude_financials=True)
        click.echo(f"Universe (current snapshot, PIT disabled): {len(universe)} stocks")

    # Load data
    financials, prices, market_caps, benchmark_prices, shares_outstanding = load_data(
        polygon_client, universe, start_date, end_date
    )

    # Filter universe to stocks with data
    valid_tickers = set(financials.keys()) & set(prices.keys()) & set(market_caps.keys())
    click.echo(f"Stocks with complete data: {len(valid_tickers)}")

    # Run backtests
    results = {}
    for model_name in models_to_run:
        click.echo(f"\n{'='*50}")
        click.echo(f"Running: {model_name}")
        click.echo('='*50)

        model_class = AVAILABLE_MODELS[model_name]
        model = model_class()

        engine = BacktestEngine(
            model=model,
            start_date=start_date,
            end_date=end_date,
            rebalance_freq=rebalance,
            portfolio_size=portfolio_size,
            membership_db=membership_db,
        )

        result = engine.run(
            financials=financials,
            prices=prices,
            market_caps=market_caps,
            benchmark_prices=benchmark_prices,
            shares_outstanding=shares_outstanding,
        )

        results[model_name] = result

        # Print summary
        m = result.metrics
        click.echo(f"\nResults for {model_name}:")
        click.echo(f"  Total Return: {m.total_return:.2%}")
        click.echo(f"  Annualized Return: {m.annualized_return:.2%}")
        click.echo(f"  Sharpe Ratio: {m.sharpe_ratio:.2f}")
        click.echo(f"  Max Drawdown: {m.max_drawdown:.2%}")

    # Save results
    output_dir = Path(output) if output else RESULTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate comparison report
    comparison = ModelComparison(results)
    report = comparison.generate_report(str(output_dir / 'comparison_report.md'))

    # Generate visualizations
    visualizer = FactorVisualizer(str(output_dir / 'charts'))
    visualizer.generate_report(results, str(output_dir / 'charts'))

    click.echo(f"\nResults saved to {output_dir}")

    # Print final comparison
    click.echo("\n" + "="*60)
    click.echo("FINAL COMPARISON")
    click.echo("="*60)
    click.echo(comparison.compare_models().to_string())


@cli.command()
@click.option('--output', '-o', default=None, help='Output directory')
def compare(output):
    """Compare model results from previous runs."""
    click.echo("Loading previous results...")
    # This would load saved results from disk
    click.echo("Use 'run --all' first to generate results for comparison")


@cli.command()
@click.option('--output', '-o', default=None, help='Output directory')
@click.option('--format', '-f', default='html', help='Output format (html, pdf)')
def report(output, format):
    """Generate analysis report."""
    click.echo("Generating report...")
    click.echo("Use 'run --all' first to generate results for the report")


@cli.command('update-data')
@click.option('--tickers', '-t', multiple=True, help='Specific tickers to update')
def update_data(tickers):
    """Update the data cache."""
    polygon_client = get_polygon_client()
    cache = CacheManager()

    if tickers:
        universe = list(tickers)
    else:
        universe_manager = UniverseManager()
        universe = universe_manager.get_sp500()

    click.echo(f"Updating data for {len(universe)} stocks...")

    from tqdm import tqdm

    for ticker in tqdm(universe, desc="Updating"):
        try:
            # Force refresh by not using cache
            polygon_client.get_financials(ticker, use_cache=False)
            polygon_client.get_prices(
                ticker,
                BACKTEST_START_DATE,
                BACKTEST_END_DATE,
                use_cache=False
            )
        except Exception as e:
            logger.warning(f"Failed to update {ticker}: {e}")

    click.echo("Data update complete")

    # Show cache stats
    stats = cache.get_cache_stats()
    click.echo("\nCache statistics:")
    for table, count in stats.items():
        click.echo(f"  {table}: {count} entries")


@cli.command('list-models')
def list_models():
    """List available factor models."""
    click.echo("\nAvailable Factor Models:")
    click.echo("="*60)

    for name, model_class in AVAILABLE_MODELS.items():
        model = model_class()
        click.echo(f"\n{name}")
        click.echo(f"  Name: {model.name}")
        click.echo(f"  Description: {model.description}")

    click.echo("\n" + "="*60)
    click.echo("To run a model: python main.py run --model <name>")
    click.echo("To run all models: python main.py run --all")


@cli.command('train-ml')
@click.option('--tune/--no-tune', default=True, help='Tune hyperparameters')
@click.option('--trials', default=50, help='Number of tuning trials')
@click.option('--output', '-o', default=None, help='Model output path')
def train_ml(tune, trials, output):
    """Train ML-based factor models."""
    try:
        from models.ml_ensemble import MLEnsembleModel
        from ml.features import FeatureEngineer
    except ImportError as e:
        click.echo(f"ML dependencies not available: {e}")
        click.echo("Install with: pip install xgboost lightgbm optuna")
        return

    click.echo("Training ML Ensemble model...")

    polygon_client = get_polygon_client()
    universe_manager = UniverseManager()
    universe = universe_manager.get_universe('sp500', exclude_financials=True)

    # Load data - ML training needs longer history than backtests
    financials, prices, market_caps, benchmark_prices, _ = load_data(
        polygon_client, universe, ML_TRAINING_START, BACKTEST_END_DATE
    )

    # Train model
    feature_engineer = FeatureEngineer()
    ml_model = MLEnsembleModel(feature_engineer=feature_engineer)

    ml_model.train(
        financials=financials,
        prices=prices,
        market_caps=market_caps,
        benchmark_prices=benchmark_prices,
        tune_hyperparams=tune,
        n_trials=trials
    )

    # Save model
    if output:
        ml_model.save(output)
    else:
        ml_model.save()

    click.echo("ML model training complete")

    # Show feature importance
    importance = ml_model.get_feature_importance()
    if importance is not None and not importance.empty:
        click.echo("\nTop 10 Most Important Features:")
        click.echo(importance.head(10).to_string())


@cli.command('current-picks')
@click.option('--model', '-m', default='magic_formula', help='Model to use')
@click.option('--n', default=30, help='Number of stocks to pick')
def current_picks(model, n):
    """Get current stock recommendations from a model."""
    if model not in AVAILABLE_MODELS:
        click.echo(f"Unknown model: {model}")
        click.echo("Available models: " + ", ".join(AVAILABLE_MODELS.keys()))
        return

    click.echo(f"Getting current picks from {model}...")

    polygon_client = get_polygon_client()
    universe_manager = UniverseManager()
    universe = universe_manager.get_universe('sp500', exclude_financials=True)

    # Load current data
    today = datetime.now().strftime('%Y-%m-%d')
    start = (datetime.now() - pd.Timedelta(days=365)).strftime('%Y-%m-%d')

    financials, prices, market_caps, _, _ = load_data(
        polygon_client, universe, start, today
    )

    # Get picks
    model_class = AVAILABLE_MODELS[model]
    model_instance = model_class()

    picks = model_instance.select_portfolio(
        financials=financials,
        prices=prices,
        market_caps=market_caps,
        n=n
    )

    click.echo(f"\n{model} Top {n} Picks:")
    click.echo("="*40)

    for i, ticker in enumerate(picks, 1):
        sector = universe_manager.get_sector(ticker) or "Unknown"
        mc = market_caps.get(ticker, 0)
        mc_str = f"${mc/1e9:.1f}B" if mc else "N/A"
        click.echo(f"{i:2}. {ticker:6} | {sector:25} | {mc_str}")


@cli.command('cache-stats')
def cache_stats():
    """Show cache statistics."""
    cache = CacheManager()
    stats = cache.get_cache_stats()

    click.echo("\nCache Statistics:")
    click.echo("="*40)
    for table, count in stats.items():
        click.echo(f"  {table}: {count} entries")


@cli.command('clear-cache')
@click.confirmation_option(prompt='Are you sure you want to clear the cache?')
def clear_cache():
    """Clear all cached data."""
    cache = CacheManager()
    cache.clear_all()
    click.echo("Cache cleared")


# =============================================================================
# Paper Trading Commands
# =============================================================================

@cli.group()
def trade():
    """Paper/live trading commands."""
    pass


@trade.command('status')
@click.option('--model', '-m', default='six_factor', help='Model to check status for')
def trade_status(model):
    """Show current trading status for a strategy."""
    try:
        from trading.alpaca_client import AlpacaClient
        from trading.strategy_trader import StrategyTrader
    except ImportError as e:
        click.echo(f"Trading dependencies not available: {e}")
        click.echo("Install with: pip install alpaca-py")
        return

    if model not in AVAILABLE_MODELS:
        click.echo(f"Unknown model: {model}")
        click.echo("Available models: " + ", ".join(AVAILABLE_MODELS.keys()))
        return

    try:
        alpaca = AlpacaClient(paper=True)
        polygon = get_polygon_client()
        model_instance = AVAILABLE_MODELS[model]()

        trader = StrategyTrader(
            model=model_instance,
            alpaca_client=alpaca,
            polygon_client=polygon
        )

        trader.print_status()

    except Exception as e:
        click.echo(f"Error: {e}")
        click.echo("\nMake sure you have set:")
        click.echo("  - ALPACA_API_KEY")
        click.echo("  - ALPACA_SECRET_KEY")


@trade.command('picks')
@click.option('--model', '-m', default='six_factor', help='Model to get picks from')
@click.option('--all', 'all_models', is_flag=True, help='Show picks from all models')
def trade_picks(model, all_models):
    """Show current stock picks from a strategy."""
    try:
        from trading.alpaca_client import AlpacaClient
        from trading.strategy_trader import StrategyTrader
    except ImportError as e:
        click.echo(f"Trading dependencies not available: {e}")
        click.echo("Install with: pip install alpaca-py")
        return

    polygon = get_polygon_client()

    if all_models:
        for model_name in AVAILABLE_MODELS.keys():
            model_instance = AVAILABLE_MODELS[model_name]()
            click.echo(f"\n{'='*50}")
            click.echo(f"{model_name.upper()}")
            click.echo('='*50)

            try:
                # Simplified - just use the current-picks logic
                universe_manager = UniverseManager()
                universe = universe_manager.get_universe('sp500', exclude_financials=True)

                today = datetime.now().strftime('%Y-%m-%d')
                start = (datetime.now() - pd.Timedelta(days=365)).strftime('%Y-%m-%d')

                financials, prices, market_caps, _, _ = load_data(
                    polygon, universe, start, today, show_progress=False
                )

                picks = model_instance.select_portfolio(
                    financials=financials,
                    prices=prices,
                    market_caps=market_caps,
                    n=30
                )

                for i, ticker in enumerate(picks[:10], 1):
                    click.echo(f"  {i:2}. {ticker}")
                if len(picks) > 10:
                    click.echo(f"  ... and {len(picks) - 10} more")

            except Exception as e:
                click.echo(f"  Error: {e}")
    else:
        if model not in AVAILABLE_MODELS:
            click.echo(f"Unknown model: {model}")
            return

        try:
            # For single model, show with Alpaca integration if available
            alpaca = AlpacaClient(paper=True)
            model_instance = AVAILABLE_MODELS[model]()

            trader = StrategyTrader(
                model=model_instance,
                alpaca_client=alpaca,
                polygon_client=polygon
            )

            trader.print_current_picks()

        except Exception as e:
            click.echo(f"Error: {e}")


@trade.command('rebalance')
@click.option('--model', '-m', default='six_factor', help='Model to rebalance')
@click.option('--dry-run', is_flag=True, help='Show trades without executing')
@click.option('--force', is_flag=True, help='Force rebalance even if within threshold')
def trade_rebalance(model, dry_run, force):
    """Execute a rebalance for a strategy."""
    try:
        from trading.alpaca_client import AlpacaClient
        from trading.strategy_trader import StrategyTrader
    except ImportError as e:
        click.echo(f"Trading dependencies not available: {e}")
        click.echo("Install with: pip install alpaca-py")
        return

    if model not in AVAILABLE_MODELS:
        click.echo(f"Unknown model: {model}")
        return

    try:
        alpaca = AlpacaClient(paper=True)
        polygon = get_polygon_client()
        model_instance = AVAILABLE_MODELS[model]()

        trader = StrategyTrader(
            model=model_instance,
            alpaca_client=alpaca,
            polygon_client=polygon
        )

        # Check if market is open
        if not alpaca.is_market_open() and not dry_run:
            click.echo("Market is closed. Use --dry-run to see planned trades.")
            next_open = alpaca.get_next_open()
            click.echo(f"Market opens: {next_open}")
            return

        click.echo(f"\nRebalancing {model}...")
        if dry_run:
            click.echo("(DRY RUN - no trades will be executed)")

        result = trader.run_rebalance(dry_run=dry_run, force=force)

        if result is None:
            click.echo("No rebalance needed (portfolio within drift threshold)")
            click.echo("Use --force to rebalance anyway")
            return

        click.echo(f"\nRebalance complete:")
        click.echo(f"  Trades executed: {len(result.trades_executed)}")
        click.echo(f"  Trades failed: {len(result.trades_failed)}")
        click.echo(f"  Portfolio value: ${result.portfolio_value_after:,.2f}")

        if result.trades_failed:
            click.echo("\nFailed trades:")
            for trade, error in result.trades_failed:
                click.echo(f"  {trade.side} {trade.symbol}: {error}")

    except Exception as e:
        click.echo(f"Error: {e}")
        import traceback
        traceback.print_exc()


@trade.command('account')
def trade_account():
    """Show Alpaca account information."""
    try:
        from trading.alpaca_client import AlpacaClient
    except ImportError as e:
        click.echo(f"Trading dependencies not available: {e}")
        click.echo("Install with: pip install alpaca-py")
        return

    try:
        alpaca = AlpacaClient(paper=True)
        account = alpaca.get_account()

        click.echo("\nAlpaca Account Info:")
        click.echo("=" * 40)
        click.echo(f"  Status: {account['status']}")
        click.echo(f"  Paper Trading: Yes")
        click.echo(f"  Currency: {account['currency']}")
        click.echo(f"\n  Portfolio Value: ${account['portfolio_value']:,.2f}")
        click.echo(f"  Cash: ${account['cash']:,.2f}")
        click.echo(f"  Buying Power: ${account['buying_power']:,.2f}")
        click.echo(f"  Equity: ${account['equity']:,.2f}")
        click.echo(f"\n  Day Trades: {account['daytrade_count']}")
        click.echo(f"  PDT Flag: {account['pattern_day_trader']}")

        # Market status
        is_open = alpaca.is_market_open()
        click.echo(f"\n  Market Open: {is_open}")
        if not is_open:
            next_open = alpaca.get_next_open()
            click.echo(f"  Next Open: {next_open}")

    except Exception as e:
        click.echo(f"Error: {e}")
        click.echo("\nMake sure you have set:")
        click.echo("  - ALPACA_API_KEY")
        click.echo("  - ALPACA_SECRET_KEY")


@trade.command('positions')
def trade_positions():
    """Show current positions."""
    try:
        from trading.alpaca_client import AlpacaClient
    except ImportError as e:
        click.echo(f"Trading dependencies not available: {e}")
        return

    try:
        alpaca = AlpacaClient(paper=True)
        positions = alpaca.get_positions()
        account = alpaca.get_account()

        if not positions:
            click.echo("\nNo open positions")
            click.echo(f"Cash available: ${account['cash']:,.2f}")
            return

        click.echo(f"\nCurrent Positions ({len(positions)}):")
        click.echo("=" * 70)
        click.echo(f"{'Symbol':<8} {'Qty':>8} {'Price':>10} {'Value':>12} {'P/L':>10} {'P/L%':>8}")
        click.echo("-" * 70)

        total_pl = 0
        for pos in positions:
            total_pl += pos.unrealized_pl
            click.echo(
                f"{pos.symbol:<8} {pos.qty:>8.2f} ${pos.current_price:>9.2f} "
                f"${pos.market_value:>11,.2f} ${pos.unrealized_pl:>9,.2f} "
                f"{pos.unrealized_plpc:>7.1%}"
            )

        click.echo("-" * 70)
        click.echo(f"{'Total':<8} {'':<8} {'':<10} ${account['equity']:>11,.2f} ${total_pl:>9,.2f}")
        click.echo(f"\nCash: ${account['cash']:,.2f}")

    except Exception as e:
        click.echo(f"Error: {e}")


@trade.command('close-all')
@click.confirmation_option(prompt='Are you sure you want to close ALL positions?')
def trade_close_all():
    """Close all positions (with confirmation)."""
    try:
        from trading.alpaca_client import AlpacaClient
    except ImportError as e:
        click.echo(f"Trading dependencies not available: {e}")
        return

    try:
        alpaca = AlpacaClient(paper=True)

        if not alpaca.is_market_open():
            click.echo("Market is closed. Cannot close positions.")
            return

        click.echo("Closing all positions...")
        orders = alpaca.close_all_positions()

        click.echo(f"Submitted {len(orders)} close orders")
        for order in orders:
            click.echo(f"  {order.side} {order.symbol}: {order.status}")

    except Exception as e:
        click.echo(f"Error: {e}")


# =============================================================================
# Strategy Rotation Commands
# =============================================================================

@cli.group()
def rotation():
    """Strategy rotation commands for meta-strategy analysis."""
    pass


@rotation.command('export-curves')
@click.option('--start-date', default='2010-01-01', help='Backtest start date')
@click.option('--end-date', default=None, help='Backtest end date (default: today)')
@click.option('--portfolio-size', default=DEFAULT_PORTFOLIO_SIZE, help='Number of stocks')
@click.option('--rebalance', default=DEFAULT_REBALANCE_FREQUENCY, help='Rebalance frequency')
@click.option('--format', '-f', default='parquet', type=click.Choice(['parquet', 'csv']), help='Output format')
def export_curves(start_date, end_date, portfolio_size, rebalance, format):
    """Export daily equity curves for all strategies."""
    from backtesting.export import StrategyDataExporter

    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')

    click.echo(f"Running backtests from {start_date} to {end_date}")
    click.echo(f"Rebalance: {rebalance}, Portfolio size: {portfolio_size}")

    # Initialize clients
    polygon_client = get_polygon_client()
    universe_manager = UniverseManager()

    # Get universe
    universe = universe_manager.get_universe('sp500', exclude_financials=True)
    click.echo(f"Universe: {len(universe)} stocks")

    # Load data
    financials, prices, market_caps, benchmark_prices, shares_outstanding = load_data(
        polygon_client, universe, start_date, end_date
    )

    # Run backtests for all models
    results = {}
    for model_name in AVAILABLE_MODELS.keys():
        click.echo(f"\nRunning: {model_name}")

        model_class = AVAILABLE_MODELS[model_name]
        model = model_class()

        engine = BacktestEngine(
            model=model,
            start_date=start_date,
            end_date=end_date,
            rebalance_freq=rebalance,
            portfolio_size=portfolio_size
        )

        result = engine.run(
            financials=financials,
            prices=prices,
            market_caps=market_caps,
            benchmark_prices=benchmark_prices,
            shares_outstanding=shares_outstanding,
            show_progress=False
        )

        results[model_name] = result
        m = result.metrics
        click.echo(f"  Return: {m.total_return:.2%}, Sharpe: {m.sharpe_ratio:.2f}")

    # Export curves
    exporter = StrategyDataExporter()
    output_path = exporter.export_results(results, format=format)

    click.echo(f"\nExported to: {output_path}")
    click.echo(f"Strategies: {list(results.keys())}")


@rotation.command('analyze-ta')
@click.option('--strategy', '-s', default=None, help='Specific strategy to analyze (default: all)')
def analyze_ta(strategy):
    """Analyze TA signals on strategy equity curves."""
    try:
        from analysis.equity_ta import EquityCurveAnalyzer
        from backtesting.export import StrategyDataExporter
    except ImportError as e:
        click.echo(f"Dependencies not available: {e}")
        click.echo("Install with: pip install pandas-ta")
        return

    exporter = StrategyDataExporter()

    try:
        df = exporter.load_strategy_curves()
    except FileNotFoundError:
        click.echo("No exported strategy curves found.")
        click.echo("Run 'rotation export-curves' first.")
        return

    analyzer = EquityCurveAnalyzer()
    strategy_values = exporter.get_all_strategy_values(df)

    strategies_to_analyze = [strategy] if strategy else strategy_values.columns.tolist()

    click.echo(f"\nAnalyzing {len(strategies_to_analyze)} strategies...")
    click.echo("=" * 70)

    for strat in strategies_to_analyze:
        if strat not in strategy_values.columns:
            click.echo(f"Strategy not found: {strat}")
            continue

        equity_curve = strategy_values[strat].dropna()
        ta_data = analyzer.analyze(equity_curve, strat)

        latest = ta_data.iloc[-1]
        click.echo(f"\n{strat.upper()}")
        click.echo("-" * 40)
        click.echo(f"  Composite Signal: {latest['composite_signal']:.3f}")
        click.echo(f"  MACD Trend:       {latest.get('macd_trend', 'N/A')}")
        click.echo(f"  RSI:              {latest.get('rsi', 'N/A'):.1f}")
        click.echo(f"  RSI Zone:         {latest.get('rsi_zone', 'N/A')}")
        click.echo(f"  SMA Trend:        {latest.get('sma_trend', 'N/A')}")
        click.echo(f"  EMA Trend:        {latest.get('ema_trend', 'N/A')}")
        click.echo(f"  Above SMA50:      {latest.get('price_above_sma_slow', 'N/A')}")


@rotation.command('backtest')
@click.option('--method', '-m', default=ROTATION_DEFAULT_METHOD,
              type=click.Choice(['binary', 'weighted', 'momentum', 'top_n']),
              help='Allocation method')
@click.option('--rebalance', '-r', default=ROTATION_REBALANCE_FREQ,
              type=click.Choice(['daily', 'weekly', 'monthly']),
              help='Rebalance frequency')
@click.option('--cost', default=10, help='Transaction cost in basis points')
def backtest(method, rebalance, cost):
    """Backtest the rotation strategy."""
    try:
        from backtesting.export import StrategyDataExporter
        from backtesting.rotation_backtest import RotationBacktester
        from models.rotation import StrategyRotationModel
    except ImportError as e:
        click.echo(f"Dependencies not available: {e}")
        return

    exporter = StrategyDataExporter()

    try:
        df = exporter.load_strategy_curves()
    except FileNotFoundError:
        click.echo("No exported strategy curves found.")
        click.echo("Run 'rotation export-curves' first.")
        return

    strategy_returns = exporter.get_all_strategy_returns(df)
    strategy_values = exporter.get_all_strategy_values(df)

    click.echo(f"\nRunning rotation backtest...")
    click.echo(f"Method: {method}")
    click.echo(f"Rebalance: {rebalance}")
    click.echo(f"Transaction cost: {cost} bps")
    click.echo(f"Date range: {strategy_returns.index.min().date()} to {strategy_returns.index.max().date()}")

    rotation_model = StrategyRotationModel(
        method=method,
        rebalance_freq=rebalance,
    )

    backtester = RotationBacktester(
        rotation_model=rotation_model,
        transaction_cost_bps=cost,
    )

    result = backtester.run(strategy_returns, strategy_values)

    # Print results
    m = result.backtest_result.metrics
    click.echo("\n" + "=" * 60)
    click.echo("ROTATION STRATEGY RESULTS")
    click.echo("=" * 60)
    click.echo(f"\nPerformance Metrics:")
    click.echo(f"  Total Return:      {m.total_return:.2%}")
    click.echo(f"  Annualized Return: {m.annualized_return:.2%}")
    click.echo(f"  Volatility:        {m.volatility:.2%}")
    click.echo(f"  Sharpe Ratio:      {m.sharpe_ratio:.2f}")
    click.echo(f"  Sortino Ratio:     {m.sortino_ratio:.2f}")
    click.echo(f"  Max Drawdown:      {m.max_drawdown:.2%}")
    click.echo(f"  Calmar Ratio:      {m.calmar_ratio:.2f}")

    click.echo(f"\nRotation Statistics:")
    click.echo(f"  Strategy Switches: {result.switch_count}")
    click.echo(f"  Avg Strategies:    {result.avg_strategies_held:.1f}")
    click.echo(f"  Total Costs:       ${result.transaction_costs_total:,.2f}")

    click.echo(f"\nBenchmark Comparison:")
    click.echo(f"  vs Equal Weight:   {result.vs_equal_weight:+.2%}")
    click.echo(f"  vs Best Strategy:  {result.vs_best_strategy:+.2%}")

    click.echo(f"\n  vs Individual Strategies:")
    for strat, alpha in sorted(result.vs_individual.items(), key=lambda x: x[1], reverse=True):
        click.echo(f"    {strat:20s}: {alpha:+.2%}")


@rotation.command('signals')
def signals():
    """View current TA signals and recommended allocation."""
    try:
        from analysis.equity_ta import EquityCurveAnalyzer
        from backtesting.export import StrategyDataExporter
        from models.rotation import StrategyRotationModel
    except ImportError as e:
        click.echo(f"Dependencies not available: {e}")
        return

    exporter = StrategyDataExporter()

    try:
        df = exporter.load_strategy_curves()
    except FileNotFoundError:
        click.echo("No exported strategy curves found.")
        click.echo("Run 'rotation export-curves' first.")
        return

    analyzer = EquityCurveAnalyzer()
    strategy_values = exporter.get_all_strategy_values(df)

    # Analyze all strategies
    strategy_ta = analyzer.analyze_all_strategies(strategy_values)
    current_signals = analyzer.get_current_signals(strategy_ta)

    click.echo("\nCurrent TA Signals")
    click.echo("=" * 70)
    click.echo(f"{'Strategy':<20} {'Signal':>10} {'MACD':>8} {'RSI':>8} {'SMA':>8} {'EMA':>8}")
    click.echo("-" * 70)

    for strat in current_signals.index:
        row = current_signals.loc[strat]
        click.echo(
            f"{strat:<20} {row['composite_signal']:>10.3f} "
            f"{row['macd_trend']:>8.0f} {row['rsi']:>8.1f} "
            f"{row['sma_trend']:>8.0f} {row['ema_trend']:>8.0f}"
        )

    # Get recommended allocation
    rotation_model = StrategyRotationModel()
    allocation = rotation_model.get_current_recommendation(strategy_values)

    click.echo("\n" + "=" * 70)
    click.echo("RECOMMENDED ALLOCATION")
    click.echo("=" * 70)
    click.echo(f"Method: {allocation.method.value}")
    click.echo(f"Date: {allocation.date}")

    click.echo(f"\n{'Strategy':<20} {'Allocation':>12}")
    click.echo("-" * 35)
    for strat, weight in sorted(allocation.allocations.items(), key=lambda x: x[1], reverse=True):
        if weight > 0:
            click.echo(f"{strat:<20} {weight:>11.1%}")


@rotation.command('compare')
@click.option('--output', '-o', default=None, help='Output directory for report')
def compare(output):
    """Compare rotation methods vs benchmarks."""
    try:
        from backtesting.export import StrategyDataExporter
        from backtesting.rotation_backtest import compare_rotation_methods, generate_rotation_comparison_report
    except ImportError as e:
        click.echo(f"Dependencies not available: {e}")
        return

    exporter = StrategyDataExporter()

    try:
        df = exporter.load_strategy_curves()
    except FileNotFoundError:
        click.echo("No exported strategy curves found.")
        click.echo("Run 'rotation export-curves' first.")
        return

    strategy_returns = exporter.get_all_strategy_returns(df)
    strategy_values = exporter.get_all_strategy_values(df)

    click.echo("\nComparing rotation methods...")
    click.echo("=" * 70)

    results = compare_rotation_methods(strategy_returns, strategy_values)

    # Generate comparison table
    comparison = generate_rotation_comparison_report(results)

    click.echo("\nRotation Method Comparison:")
    click.echo(comparison.to_string(index=False))

    # Also show individual strategy results
    click.echo("\n" + "=" * 70)
    click.echo("Individual Strategy Results (for comparison):")
    click.echo("-" * 70)

    for strategy in strategy_returns.columns:
        strat_returns = strategy_returns[strategy]
        total_return = (1 + strat_returns).prod() - 1
        ann_return = (1 + total_return) ** (252 / len(strat_returns)) - 1
        volatility = strat_returns.std() * (252 ** 0.5)
        sharpe = (strat_returns.mean() - 0.04/252) / strat_returns.std() * (252 ** 0.5) if strat_returns.std() > 0 else 0

        click.echo(f"{strategy:<20} Return: {total_return:>8.2%}  Ann: {ann_return:>8.2%}  Vol: {volatility:>8.2%}  Sharpe: {sharpe:>6.2f}")

    # Equal weight benchmark
    ew_returns = strategy_returns.mean(axis=1)
    ew_total = (1 + ew_returns).prod() - 1
    ew_ann = (1 + ew_total) ** (252 / len(ew_returns)) - 1
    ew_vol = ew_returns.std() * (252 ** 0.5)
    ew_sharpe = (ew_returns.mean() - 0.04/252) / ew_returns.std() * (252 ** 0.5) if ew_returns.std() > 0 else 0

    click.echo("-" * 70)
    click.echo(f"{'Equal Weight':<20} Return: {ew_total:>8.2%}  Ann: {ew_ann:>8.2%}  Vol: {ew_vol:>8.2%}  Sharpe: {ew_sharpe:>6.2f}")

    # Save report if output specified
    if output:
        output_dir = Path(output)
        output_dir.mkdir(parents=True, exist_ok=True)
        comparison.to_csv(output_dir / 'rotation_comparison.csv', index=False)
        click.echo(f"\nReport saved to {output_dir / 'rotation_comparison.csv'}")


# =============================================================================
# Shadow Tracking Commands (parallel-strategy monitoring)
# =============================================================================

@cli.group()
def shadow():
    """Shadow-track all strategies in parallel for the dashboard / rotation engine."""
    pass


@shadow.command('init')
def shadow_init():
    """Create or reset the shadow-tracking SQLite schema."""
    from tracking import ShadowDB
    db = ShadowDB()
    click.echo(f"Shadow DB ready at {db.db_path}")


@shadow.command('build-membership')
def shadow_build_membership():
    """Fetch the S&P 500 historical-membership tables from Wikipedia."""
    from data.sp500_membership import MembershipDB
    db = MembershipDB()
    info = db.refresh_from_wikipedia()
    click.echo(
        f"Members: {info['current_members']}, changes: {info['changes']}, "
        f"fetched_at: {info['fetched_at']}"
    )
    click.echo(f"DB path: {db.db_path}")


@shadow.command('membership-status')
@click.option('--date', default=None, help='Show member count on this date (YYYY-MM-DD)')
def shadow_membership_status(date):
    """Show summary of the historical-membership DB."""
    from data.sp500_membership import MembershipDB
    db = MembershipDB()
    s = db.status()
    click.echo(
        f"Members (today): {s['current_members']}, changes: {s['changes']}\n"
        f"Earliest change: {s['earliest_change']}, latest: {s['latest_change']}\n"
        f"Last fetch: {s.get('last_fetch', 'n/a')}"
    )
    if date:
        members = db.members_on(date)
        click.echo(f"Members on {date}: {len(members)}")


@shadow.command('backfill')
@click.option('--start-date', default='2019-01-01', help='Backfill start date')
@click.option('--end-date', default=None, help='Backfill end date (default: today)')
@click.option('-m', '--model', 'models', multiple=True, help='Subset of models (default: all)')
@click.option('--portfolio-size', default=DEFAULT_PORTFOLIO_SIZE, help='Number of stocks')
@click.option('--rebalance', default=DEFAULT_REBALANCE_FREQUENCY, help='Rebalance frequency')
@click.option('--no-pit-membership', is_flag=True, help='Disable point-in-time S&P 500 membership filter')
def shadow_backfill(start_date, end_date, models, portfolio_size, rebalance, no_pit_membership):
    """Populate the shadow DB with full historical equity curves for each strategy."""
    from tracking import ShadowDB
    from tracking.snapshot import backfill_strategy

    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')

    targets = list(models) if models else list(AVAILABLE_MODELS.keys())
    for m in targets:
        if m not in AVAILABLE_MODELS:
            click.echo(f"Unknown model: {m}")
            return

    click.echo(f"Backfill {start_date} -> {end_date}, models: {', '.join(targets)}")

    polygon_client = get_polygon_client()
    universe_manager = UniverseManager()

    membership_db = None
    if not no_pit_membership:
        try:
            from data.sp500_membership import MembershipDB
            membership_db = MembershipDB()
            membership_db.status()
            universe = universe_manager.get_universe_union(
                start_date, end_date, exclude_financials=True
            )
            click.echo(f"Universe (point-in-time union): {len(universe)} tickers")
        except Exception as e:
            click.echo(f"Falling back to current S&P 500 snapshot ({e})")
            membership_db = None
            universe = universe_manager.get_universe('sp500', exclude_financials=True)
            click.echo(f"Universe (current snapshot): {len(universe)} stocks")
    else:
        universe = universe_manager.get_universe('sp500', exclude_financials=True)
        click.echo(f"Universe (current snapshot, PIT disabled): {len(universe)} stocks")

    financials, prices, market_caps, benchmark_prices, shares_outstanding = load_data(
        polygon_client, universe, start_date, end_date
    )
    click.echo(f"Loaded: {len(prices)} prices, {len(market_caps)} market caps")

    db = ShadowDB()
    for name in targets:
        click.echo(f"\nBackfilling {name}...")
        model = AVAILABLE_MODELS[name]()
        result = backfill_strategy(
            db=db,
            strategy_name=name,
            model=model,
            financials=financials,
            prices=prices,
            market_caps=market_caps,
            benchmark_prices=benchmark_prices,
            shares_outstanding=shares_outstanding,
            start_date=start_date,
            end_date=end_date,
            rebalance_freq=rebalance,
            portfolio_size=portfolio_size,
            show_progress=False,
            membership_db=membership_db,
        )
        m = result.metrics
        click.echo(
            f"  {name}: total {m.total_return:.2%}, Sharpe {m.sharpe_ratio:.2f}, "
            f"final ${result.final_value:,.0f}"
        )
    click.echo(f"\nShadow DB at {db.db_path}")


@shadow.command('update')
@click.option('--target-date', default=None, help='Date to update through (default: today)')
@click.option('-m', '--model', 'models', multiple=True, help='Subset of models (default: all)')
@click.option('--portfolio-size', default=DEFAULT_PORTFOLIO_SIZE, help='Number of stocks')
@click.option('--rebalance', default=DEFAULT_REBALANCE_FREQUENCY, help='Rebalance frequency')
def shadow_update(target_date, models, portfolio_size, rebalance):
    """Incremental daily update for the shadow DB."""
    from tracking import ShadowDB
    from tracking.snapshot import update_strategy_daily

    if target_date is None:
        target_date = datetime.now().strftime('%Y-%m-%d')

    db = ShadowDB()
    targets = list(models) if models else db.list_strategies()
    if not targets:
        click.echo("No strategies found in shadow DB. Run `shadow backfill` first.")
        return

    earliest_existing = None
    for name in targets:
        latest = db.get_latest_equity_date(name)
        if latest and (earliest_existing is None or latest < earliest_existing):
            earliest_existing = latest
    buffer_start = (
        pd.Timestamp(earliest_existing) - pd.Timedelta(days=60)
    ).strftime('%Y-%m-%d') if earliest_existing else '2019-01-01'

    polygon_client = get_polygon_client()
    universe = UniverseManager().get_universe('sp500', exclude_financials=True)
    financials, prices, market_caps, benchmark_prices, shares_outstanding = load_data(
        polygon_client, universe, buffer_start, target_date
    )

    for name in targets:
        if name not in AVAILABLE_MODELS:
            click.echo(f"Skipping unknown model {name}")
            continue
        model = AVAILABLE_MODELS[name]()
        out = update_strategy_daily(
            db=db,
            strategy_name=name,
            model=model,
            financials=financials,
            prices=prices,
            market_caps=market_caps,
            benchmark_prices=benchmark_prices,
            shares_outstanding=shares_outstanding,
            target_date=target_date,
            rebalance_freq=rebalance,
            portfolio_size=portfolio_size,
        )
        if out.get('skipped'):
            click.echo(f"  {name}: skipped ({out.get('reason')})")
        else:
            click.echo(f"  {name}: +{out.get('rows_added', 0)} rows through {target_date}")


@shadow.command('status')
def shadow_status():
    """Show one-line summary per strategy currently in the shadow DB."""
    from tracking import ShadowDB
    db = ShadowDB()
    summary = db.summary()
    if summary.empty:
        click.echo("Shadow DB is empty. Run `shadow backfill` first.")
        return

    click.echo(f"\n{'Strategy':<22} {'Last':<12} {'Equity':>14} {'Total Ret':>10} {'Worst DD':>10} {'Days':>6}")
    click.echo("-" * 80)
    for _, row in summary.iterrows():
        click.echo(
            f"{row['strategy']:<22} {row['last_date']:<12} "
            f"${row['last_equity']:>12,.0f}   "
            f"{row['last_cumulative_return']:>9.2%} "
            f"{row['worst_drawdown']:>9.2%} "
            f"{int(row['n_days']):>6d}"
        )


@shadow.command('dashboard')
@click.option('--port', default=8501, type=int, help='Streamlit port')
def shadow_dashboard(port):
    """Launch the Streamlit dashboard against the shadow DB."""
    import subprocess
    app = Path(__file__).resolve().parent / "dashboard" / "app.py"
    if not app.exists():
        click.echo(f"dashboard/app.py not found at {app}")
        return
    cmd = [sys.executable, "-m", "streamlit", "run", str(app), "--server.port", str(port)]
    click.echo(f"Launching dashboard: {' '.join(cmd)}")
    subprocess.run(cmd)


@shadow.command('curves')
@click.option('-m', '--model', 'model_name', required=True, help='Model to export')
@click.option('--output', '-o', default=None, help='Output CSV path (default stdout summary)')
@click.option('--start-date', default=None, help='Start date filter')
@click.option('--end-date', default=None, help='End date filter')
def shadow_curves(model_name, output, start_date, end_date):
    """Export the equity curve for one strategy."""
    from tracking import ShadowDB
    db = ShadowDB()
    df = db.get_equity_curve(model_name, start=start_date, end=end_date)
    if df.empty:
        click.echo(f"No data for {model_name}.")
        return
    if output:
        df.to_csv(output, index=False)
        click.echo(f"Saved {len(df)} rows to {output}")
    else:
        click.echo(df.tail(20).to_string(index=False))
        click.echo(f"\n({len(df)} total rows)")


if __name__ == '__main__':
    cli()
