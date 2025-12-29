# Paper Trading Setup Guide

This guide walks you through setting up paper trading with Alpaca for your factor investing strategies.

---

## Prerequisites

1. **Alpaca Account**: Sign up for a free account at [alpaca.markets](https://alpaca.markets)
2. **Python Dependencies**: Install the required packages

```bash
pip install alpaca-py python-dotenv
```

---

## Step 1: Get Your Alpaca API Keys

1. Log into your Alpaca account
2. Go to **Paper Trading** (not Live Trading)
3. Click on **API Keys** in the sidebar
4. Click **Generate New Keys**
5. Copy both the **API Key ID** and **Secret Key**

> **Important**: Keep your secret key safe! You won't be able to see it again.

---

## Step 2: Configure API Keys

### Option A: Use .env File (Recommended)

1. Open the `.env` file in the project root (or copy from `.env.example`):
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your Alpaca keys:
   ```
   POLYGON_API_KEY=your_polygon_key_here
   ALPACA_API_KEY=your_alpaca_key_here
   ALPACA_SECRET_KEY=your_alpaca_secret_here
   ```

> **Note**: The `.env` file is in `.gitignore` so your keys won't be accidentally committed.

### Option B: Environment Variables

#### Windows (PowerShell)
```powershell
$env:ALPACA_API_KEY = "your_api_key_here"
$env:ALPACA_SECRET_KEY = "your_secret_key_here"
```

#### Mac/Linux
```bash
export ALPACA_API_KEY="your_api_key_here"
export ALPACA_SECRET_KEY="your_secret_key_here"
```

---

## Step 3: Verify Your Setup

Check that your API keys are working:

```bash
python main.py trade account
```

You should see output like:
```
Alpaca Account Info:
========================================
  Status: ACTIVE
  Paper Trading: Yes
  Currency: USD

  Portfolio Value: $100,000.00
  Cash: $100,000.00
  Buying Power: $200,000.00
  Equity: $100,000.00

  Day Trades: 0
  PDT Flag: False

  Market Open: True
```

---

## Available Trading Commands

### Check Account Status
```bash
python main.py trade account
```

### View Current Positions
```bash
python main.py trade positions
```

### Get Model Stock Picks
```bash
# Single model
python main.py trade picks --model six_factor

# All models
python main.py trade picks --all
```

### View Strategy Status
```bash
python main.py trade status --model six_factor
```

### Execute a Rebalance

```bash
# Dry run (see what trades would be made)
python main.py trade rebalance --model six_factor --dry-run

# Actual rebalance (requires market to be open)
python main.py trade rebalance --model six_factor

# Force rebalance even if within drift threshold
python main.py trade rebalance --model six_factor --force
```

### Close All Positions
```bash
python main.py trade close-all
```

---

## Running Multiple Strategies

If you want to run multiple strategies, you'll need separate Alpaca accounts for each. Alpaca supports sub-accounts for this purpose.

For now, you can manually switch between strategies by running rebalance with different `--model` flags, but this will replace your existing positions.

---

## Automated Scheduling

To run automatic rebalancing on a schedule:

```bash
# Quarterly rebalancing (recommended for most strategies)
python -m trading.scheduler --model six_factor --frequency quarterly

# Monthly rebalancing
python -m trading.scheduler --model garp --frequency monthly --time 10:00

# Weekly rebalancing (higher turnover)
python -m trading.scheduler --model six_factor --frequency weekly --day monday

# Dry run mode (for testing)
python -m trading.scheduler --model six_factor --frequency quarterly --dry-run

# Run immediately (then exit)
python -m trading.scheduler --model six_factor --run-now
```

### Running as a Background Service

#### Windows (Task Scheduler)
1. Open Task Scheduler
2. Create a new task
3. Set trigger: Daily at market open (e.g., 9:35 AM ET)
4. Action: Run `python -m trading.scheduler --model six_factor --run-now`

#### Linux/Mac (cron)
```bash
# Run quarterly check at 10:00 AM on first day of each quarter
0 10 1 1,4,7,10 * cd /path/to/factor_investing && python -m trading.scheduler --model six_factor --run-now
```

---

## Strategy Recommendations for Paper Trading

Based on our backtesting research:

| Strategy | Best For | Rebalance Frequency |
|----------|----------|---------------------|
| **six_factor** | Maximum returns, bull markets | Quarterly |
| **garp** | Bear market protection, stability | Quarterly |
| **three_factor** | Balanced approach | Quarterly |
| **quality_value** | Conservative, dividend-like | Quarterly |
| **magic_formula** | Simple, classic value | Quarterly |
| **piotroski** | Deep value turnarounds | Quarterly |

### Suggested Starting Point

If you're new to this, start with:

```bash
# See what six_factor would buy
python main.py trade picks --model six_factor

# Do a dry run to see the trades
python main.py trade rebalance --model six_factor --dry-run

# When ready, execute (during market hours)
python main.py trade rebalance --model six_factor
```

---

## Important Notes

1. **Paper trading is simulated** - No real money is at risk
2. **Alpaca paper accounts start with $100,000** virtual cash
3. **Market hours**: 9:30 AM - 4:00 PM Eastern Time, weekdays
4. **Rebalancing outside market hours** will fail - use `--dry-run` to test

---

## Monitoring Your Portfolio

After rebalancing, you can monitor your portfolio:

```bash
# Check positions
python main.py trade positions

# Check strategy status
python main.py trade status --model six_factor
```

Trade logs are saved to `results/trading_logs/` for record keeping.

---

## Troubleshooting

### "Alpaca SDK not installed"
```bash
pip install alpaca-py
```

### "API credentials required"
Make sure both `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` are set.

### "Market is closed"
Trading only works during market hours. Use `--dry-run` to test outside hours.

### "Insufficient buying power"
Your paper account may have too many positions or insufficient cash. Use `trade close-all` to start fresh.

---

## Next Steps

1. Start with paper trading for at least 1 quarter
2. Monitor performance vs. backtest expectations
3. Adjust strategy selection based on market conditions
4. When confident, consider live trading (change `ALPACA_PAPER = False` in config.py)

**Remember: Past backtested performance does not guarantee future results!**
