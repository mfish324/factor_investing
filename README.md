# Factor Investing Analysis Application

A comprehensive Python application for factor-based stock analysis and backtesting. This system calculates value, quality, growth, momentum, and sentiment factors for stocks, implements several well-known factor models, and backtests their historical performance.

## Features

- **Multiple Factor Categories**: Value, Quality, Growth, Momentum, Volatility, and Sentiment
- **6 Traditional Factor Models**: Magic Formula, Piotroski F-Score, GARP, Quality-Value, Three-Factor, Six-Factor
- **ML-Based Models**: XGBoost/LightGBM rankers with hyperparameter tuning
- **Comprehensive Backtesting**: Walk-forward testing with configurable rebalancing
- **Performance Analytics**: Sharpe, Sortino, Calmar ratios, drawdown analysis
- **Interactive Visualizations**: Plotly-based charts and HTML reports

## Installation

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Unix/macOS)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Set your Polygon.io API key:

```bash
# Windows
set POLYGON_API_KEY=your_key_here

# Unix/macOS
export POLYGON_API_KEY=your_key_here
```

## Usage

### List Available Models

```bash
python main.py list-models
```

### Run Backtests

```bash
# Run all models
python main.py run --all

# Run specific model
python main.py run --model magic_formula

# Custom parameters
python main.py run --model piotroski --start-date 2020-01-01 --end-date 2024-01-01 --portfolio-size 20
```

### Get Current Stock Picks

```bash
python main.py current-picks --model magic_formula --n 30
```

### Train ML Models

```bash
python main.py train-ml --tune --trials 50
```

### Data Management

```bash
# Update data cache
python main.py update-data

# View cache statistics
python main.py cache-stats

# Clear cache
python main.py clear-cache
```

## Factor Models

### Traditional Models

| Model | Description | Key Factors |
|-------|-------------|-------------|
| Magic Formula | Greenblatt's strategy | Earnings Yield + ROIC |
| Piotroski F-Score | 9-point quality score | Profitability, Leverage, Efficiency |
| GARP | Growth at Reasonable Price | PEG Ratio |
| Quality-Value | Composite model | ROE/ROIC + P/E/P/B |
| Three-Factor | Balanced approach | Value + Quality + Growth |
| Six-Factor | Comprehensive | + Sentiment + Momentum + Volatility |

### ML Models

| Model | Description |
|-------|-------------|
| ML Ensemble | XGBoost/LightGBM on all factors |
| Multi-Model | Ensemble of RF, XGBoost, LightGBM |

## Project Structure

```
factor_investing/
├── config.py              # Configuration settings
├── main.py                # CLI entry point
├── requirements.txt       # Dependencies
├── data/
│   ├── polygon_client.py  # Polygon API wrapper
│   ├── cache.py           # SQLite caching
│   └── universe.py        # Stock universe management
├── factors/
│   ├── base.py            # Base factor class
│   ├── value.py           # Value factors
│   ├── quality.py         # Quality factors
│   ├── growth.py          # Growth factors
│   ├── momentum.py        # Momentum factors
│   └── sentiment.py       # Sentiment factors
├── models/
│   ├── base.py            # Abstract model class
│   ├── magic_formula.py   # Magic Formula
│   ├── piotroski.py       # Piotroski F-Score
│   ├── garp.py            # GARP
│   ├── quality_value.py   # Quality-Value
│   ├── three_factor.py    # Three-Factor
│   ├── six_factor.py      # Six-Factor
│   └── ml_ensemble.py     # ML models
├── backtesting/
│   ├── engine.py          # Backtest execution
│   ├── portfolio.py       # Portfolio management
│   └── metrics.py         # Performance metrics
├── ml/
│   ├── features.py        # Feature engineering
│   ├── models.py          # ML model definitions
│   ├── training.py        # Training pipeline
│   └── evaluation.py      # Model evaluation
├── analysis/
│   ├── comparison.py      # Model comparison
│   └── visualization.py   # Charts and reports
└── results/               # Output directory
```

## Factor Definitions

### Value Factors
- Earnings Yield (EBIT / EV)
- P/E, P/B, P/S, P/FCF
- EV/EBITDA

### Quality Factors
- ROE, ROA, ROIC
- Gross/Operating/Net Margins
- Debt-to-Equity, Current Ratio
- Piotroski F-Score (0-9)

### Growth Factors
- Revenue Growth (YoY and 3Y CAGR)
- Earnings Growth (YoY and 3Y CAGR)
- Asset Growth

### Momentum Factors
- 12-1 Month Price Momentum
- Relative Strength vs Market
- Distance from 52-Week High
- Moving Average Trend

### Sentiment Factors
- Net Insider Buying
- Insider Buy/Sell Ratio
- Cluster Buying Signal
- Institutional Ownership

## Performance Metrics

- Total and Annualized Return
- Sharpe and Sortino Ratios
- Maximum Drawdown and Calmar Ratio
- Alpha, Beta, Information Ratio
- Win Rate and Profit Factor

## Requirements

- Python 3.11+
- Polygon.io API key (free tier works)
- See requirements.txt for full dependencies

## Optional Dependencies

For ML models:
```bash
pip install xgboost lightgbm optuna
```

For enhanced visualizations:
```bash
pip install seaborn shap
```
