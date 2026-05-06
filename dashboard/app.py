"""
Streamlit dashboard for parallel-strategy monitoring.

Reads from data/shadow.db. Run with:

    python main.py shadow dashboard
    # or
    streamlit run dashboard/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Make project imports work when running via `streamlit run dashboard/app.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tracking import ShadowDB
from data.polygon_client import PolygonClient

st.set_page_config(
    page_title="Factor Investing — Strategy Monitor",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------- data loaders (cached) ----------


@st.cache_data(ttl=300)
def load_summary() -> pd.DataFrame:
    db = ShadowDB()
    return db.summary()


@st.cache_data(ttl=300)
def load_equity_curves(strategies: tuple[str, ...]) -> pd.DataFrame:
    db = ShadowDB()
    frames = []
    for s in strategies:
        df = db.get_equity_curve(s)
        if not df.empty:
            df = df.assign(strategy=s)
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"])
    return out


@st.cache_data(ttl=300)
def load_current_picks(strategy: str) -> pd.DataFrame:
    db = ShadowDB()
    df = db.get_picks_history(strategy)
    if df.empty:
        return df
    latest_date = df["rebalance_date"].max()
    return df[df["rebalance_date"] == latest_date].sort_values("rank")


@st.cache_data(ttl=300)
def load_picks_diff(strategy: str) -> dict:
    """Compare latest rebalance picks to the prior rebalance for a strategy."""
    db = ShadowDB()
    df = db.get_picks_history(strategy)
    if df.empty:
        return {"added": [], "removed": [], "kept": [], "latest_date": None, "prior_date": None}
    dates = sorted(df["rebalance_date"].unique())
    if len(dates) < 2:
        latest_set = set(df[df["rebalance_date"] == dates[-1]]["ticker"])
        return {"added": list(latest_set), "removed": [], "kept": [], "latest_date": dates[-1], "prior_date": None}
    latest, prior = dates[-1], dates[-2]
    latest_set = set(df[df["rebalance_date"] == latest]["ticker"])
    prior_set = set(df[df["rebalance_date"] == prior]["ticker"])
    return {
        "added": sorted(latest_set - prior_set),
        "removed": sorted(prior_set - latest_set),
        "kept": sorted(latest_set & prior_set),
        "latest_date": latest,
        "prior_date": prior,
    }


@st.cache_data(ttl=600)
def load_spy_curve(start: str, end: str, initial_capital: float = 100_000.0) -> pd.DataFrame:
    """Build SPY equity curve from the polygon cache for benchmark comparison."""
    try:
        client = PolygonClient()
        df = client.get_prices("SPY", start, end)
    except Exception as e:
        st.warning(f"Could not load SPY benchmark: {e}")
        return pd.DataFrame()
    if df is None or df.empty or "close" not in df.columns:
        return pd.DataFrame()
    if "date" in df.columns:
        df = df.assign(date=pd.to_datetime(df["date"]))
    else:
        df = df.assign(date=pd.to_datetime(df.index))
    df = df.sort_values("date").reset_index(drop=True)
    end_ts = pd.Timestamp(end)
    df = df[df["date"] <= end_ts]
    rets = df["close"].pct_change().fillna(0)
    cum = (1 + rets).cumprod()
    rolling_max = cum.cummax()
    drawdown = cum / rolling_max - 1
    return pd.DataFrame(
        {
            "date": df["date"].values,
            "equity": (initial_capital * cum).values,
            "daily_return": rets.values,
            "cumulative_return": (cum - 1).values,
            "drawdown": drawdown.values,
            "strategy": "SPY (benchmark)",
        }
    )


@st.cache_data(ttl=300)
def load_returns_matrix(strategies: tuple[str, ...]) -> pd.DataFrame:
    """Wide DataFrame: index=date, columns=strategy, values=daily_return."""
    curves = load_equity_curves(strategies)
    if curves.empty:
        return pd.DataFrame()
    wide = curves.pivot(index="date", columns="strategy", values="daily_return")
    return wide


# ---------- regime signals ----------


def _trend_signal(equity: pd.Series, fast: int = 20, slow: int = 50) -> str:
    """Simple SMA-crossover regime tag."""
    if len(equity) < slow + 1:
        return "neutral"
    sma_fast = equity.rolling(fast).mean()
    sma_slow = equity.rolling(slow).mean()
    if pd.isna(sma_fast.iloc[-1]) or pd.isna(sma_slow.iloc[-1]):
        return "neutral"
    diff = sma_fast.iloc[-1] - sma_slow.iloc[-1]
    pct = diff / sma_slow.iloc[-1] if sma_slow.iloc[-1] else 0
    if pct > 0.02:
        return "bull"
    if pct < -0.02:
        return "bear"
    return "neutral"


def _rsi(equity: pd.Series, period: int = 14) -> float:
    """Wilder RSI on the equity curve. Returns latest value or 50."""
    if len(equity) < period + 1:
        return 50.0
    delta = equity.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    last = rsi.iloc[-1]
    return float(last) if not pd.isna(last) else 50.0


def regime_signals(curves: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for strategy, group in curves.groupby("strategy"):
        equity = group.sort_values("date")["equity"]
        trend = _trend_signal(equity)
        rsi = _rsi(equity)
        last = group.sort_values("date").iloc[-1]
        rows.append(
            {
                "Strategy": strategy,
                "Trend (20/50 SMA)": trend,
                "RSI": round(rsi, 1),
                "Drawdown": last["drawdown"],
                "Last Equity": last["equity"],
            }
        )
    return pd.DataFrame(rows).sort_values("Last Equity", ascending=False)


# ---------- UI ----------


def main():
    st.title("Factor Investing — Strategy Monitor")

    summary = load_summary()
    if summary.empty:
        st.warning(
            "Shadow DB is empty. Run `python main.py shadow backfill` first."
        )
        return

    available_strategies = summary["strategy"].tolist()

    # --- sidebar ---
    st.sidebar.header("Filters")

    range_preset = st.sidebar.selectbox(
        "Date range", ["All", "Last 1Y", "Last 3Y", "Last 5Y", "Custom"], index=0
    )
    last_date = pd.Timestamp(summary["last_date"].max())
    start_date = pd.Timestamp(summary["start_date"].min())
    if range_preset == "Last 1Y":
        start_date = last_date - pd.DateOffset(years=1)
    elif range_preset == "Last 3Y":
        start_date = last_date - pd.DateOffset(years=3)
    elif range_preset == "Last 5Y":
        start_date = last_date - pd.DateOffset(years=5)
    elif range_preset == "Custom":
        custom = st.sidebar.date_input(
            "Custom range",
            value=(start_date.date(), last_date.date()),
            min_value=start_date.date(),
            max_value=last_date.date(),
        )
        if isinstance(custom, tuple) and len(custom) == 2:
            start_date = pd.Timestamp(custom[0])
            last_date = pd.Timestamp(custom[1])

    strategies_selected = st.sidebar.multiselect(
        "Strategies", available_strategies, default=available_strategies
    )
    show_benchmark = st.sidebar.checkbox("Overlay SPY benchmark", value=True)

    if not strategies_selected:
        st.info("Pick at least one strategy.")
        return

    curves = load_equity_curves(tuple(strategies_selected))
    if curves.empty:
        st.warning("No equity data for the selected strategies.")
        return
    curves = curves[(curves["date"] >= start_date) & (curves["date"] <= last_date)]
    if curves.empty:
        st.warning("No equity data in the selected date range.")
        return

    # Re-anchor cumulative_return so it starts at 0 on the filtered window
    def reanchor(group: pd.DataFrame) -> pd.DataFrame:
        first_eq = group.sort_values("date")["equity"].iloc[0]
        group = group.assign(
            window_return=group["equity"] / first_eq - 1,
            window_equity=group["equity"] / first_eq * 100_000.0,
        )
        running_max = group["window_equity"].cummax()
        group = group.assign(window_drawdown=group["window_equity"] / running_max - 1)
        return group

    curves = curves.groupby("strategy", group_keys=False).apply(reanchor)

    if show_benchmark:
        spy = load_spy_curve(
            start_date.strftime("%Y-%m-%d"), last_date.strftime("%Y-%m-%d")
        )
        if not spy.empty:
            spy_r = spy.copy()
            first_eq = spy_r["equity"].iloc[0]
            spy_r["window_return"] = spy_r["equity"] / first_eq - 1
            spy_r["window_equity"] = spy_r["equity"] / first_eq * 100_000.0
            running_max = spy_r["window_equity"].cummax()
            spy_r["window_drawdown"] = spy_r["window_equity"] / running_max - 1
            curves = pd.concat([curves, spy_r], ignore_index=True)

    # --- summary ---
    st.subheader("Performance Summary")
    perf_rows = []
    for strategy, group in curves.groupby("strategy"):
        group = group.sort_values("date")
        n_days = len(group)
        if n_days < 2:
            continue
        years = n_days / 252
        total = float(group["window_return"].iloc[-1])
        ann = (1 + total) ** (1 / years) - 1 if years > 0 else 0
        daily = group["daily_return"].dropna()
        vol = daily.std() * np.sqrt(252)
        sharpe = (ann - 0.04) / vol if vol > 0 else 0
        max_dd = float(group["window_drawdown"].min())
        perf_rows.append(
            {
                "Strategy": strategy,
                "Total": f"{total:.1%}",
                "Annualized": f"{ann:.1%}",
                "Volatility": f"{vol:.1%}",
                "Sharpe (rf=4%)": f"{sharpe:.2f}",
                "Max DD": f"{max_dd:.1%}",
                "Final Equity ($100k start)": f"${group['window_equity'].iloc[-1]:,.0f}",
            }
        )
    perf_df = pd.DataFrame(perf_rows).sort_values(
        "Final Equity ($100k start)", ascending=False, key=lambda c: c.str.replace(r"[\$,]", "", regex=True).astype(float)
    )
    st.dataframe(perf_df, hide_index=True, use_container_width=True)

    # --- cumulative returns ---
    st.subheader("Cumulative Return")
    fig = px.line(
        curves.sort_values("date"),
        x="date",
        y="window_return",
        color="strategy",
        labels={"window_return": "Return", "date": "Date"},
    )
    fig.update_layout(yaxis_tickformat=".0%", hovermode="x unified", height=460)
    st.plotly_chart(fig, use_container_width=True)

    # --- drawdown ---
    st.subheader("Drawdown")
    fig_dd = px.line(
        curves.sort_values("date"),
        x="date",
        y="window_drawdown",
        color="strategy",
        labels={"window_drawdown": "Drawdown", "date": "Date"},
    )
    fig_dd.update_layout(yaxis_tickformat=".0%", hovermode="x unified", height=360)
    st.plotly_chart(fig_dd, use_container_width=True)

    # --- regime signals ---
    st.subheader("Regime Signals")
    sig_curves = curves[curves["strategy"] != "SPY (benchmark)"]
    sig_df = regime_signals(sig_curves)
    if not sig_df.empty:
        sig_display = sig_df.copy()
        sig_display["Drawdown"] = sig_display["Drawdown"].map(lambda x: f"{x:.1%}")
        sig_display["Last Equity"] = sig_display["Last Equity"].map(lambda x: f"${x:,.0f}")

        def highlight_trend(val):
            colors = {"bull": "#1f7a1f", "bear": "#a31b1b", "neutral": "#888"}
            color = colors.get(val, "#888")
            return f"color: white; background-color: {color}; font-weight: 600"

        styled = sig_display.style.map(highlight_trend, subset=["Trend (20/50 SMA)"])
        st.dataframe(styled, hide_index=True, use_container_width=True)
        st.caption(
            "Trend: 20-DMA vs 50-DMA on the strategy's equity curve. "
            "Bull = +2% above, Bear = -2% below, Neutral otherwise. "
            "RSI < 30 oversold, > 70 overbought."
        )

    # --- correlation matrix ---
    st.subheader("Daily-Return Correlation")
    returns_wide = load_returns_matrix(tuple(s for s in strategies_selected))
    if not returns_wide.empty:
        returns_wide = returns_wide.loc[
            (returns_wide.index >= start_date) & (returns_wide.index <= last_date)
        ]
        corr = returns_wide.corr()
        if not corr.empty:
            heat = go.Figure(
                data=go.Heatmap(
                    z=corr.values,
                    x=corr.columns,
                    y=corr.index,
                    colorscale="RdBu",
                    zmid=0,
                    zmin=-1,
                    zmax=1,
                    text=corr.round(2).values,
                    texttemplate="%{text}",
                    colorbar=dict(title="ρ"),
                )
            )
            heat.update_layout(height=480, margin=dict(t=20, b=20))
            st.plotly_chart(heat, use_container_width=True)
            st.caption(
                "Lower correlation between two strategies means combining them gives more diversification."
            )

    # --- current picks ---
    st.subheader("Current Picks (latest rebalance)")
    cols = st.columns(min(3, len(strategies_selected)))
    for i, strategy in enumerate(strategies_selected):
        with cols[i % len(cols)]:
            picks = load_current_picks(strategy)
            diff = load_picks_diff(strategy)
            if picks.empty:
                st.write(f"**{strategy}**: no picks recorded.")
                continue
            latest = picks["rebalance_date"].iloc[0]
            with st.expander(
                f"**{strategy}** — {pd.Timestamp(latest).date()} ({len(picks)} stocks)",
                expanded=False,
            ):
                st.write(
                    f"Rebalance changed by **{len(diff['added'])} adds / "
                    f"{len(diff['removed'])} drops** vs prior rebalance "
                    f"({pd.Timestamp(diff['prior_date']).date() if diff['prior_date'] else 'n/a'})"
                )
                if diff["added"]:
                    st.write("**Added:** " + ", ".join(diff["added"]))
                if diff["removed"]:
                    st.write("**Dropped:** " + ", ".join(diff["removed"]))
                st.dataframe(
                    picks[["rank", "ticker", "score"]].rename(
                        columns={"rank": "Rank", "ticker": "Ticker", "score": "Score"}
                    ),
                    hide_index=True,
                    use_container_width=True,
                )

    st.caption(
        f"Data through {summary['last_date'].max()} — refresh after `python main.py shadow update`."
    )


if __name__ == "__main__":
    main()
