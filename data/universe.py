"""
Stock universe management.
Handles S&P 500 constituents and data filtering.
"""

import logging
from typing import List, Optional, Dict
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)


# Static S&P 500 list (as of late 2024)
# In production, this should be fetched dynamically or from a data provider
SP500_TICKERS = [
    "AAPL", "ABBV", "ABT", "ACN", "ADBE", "ADI", "ADM", "ADP", "ADSK", "AEE",
    "AEP", "AES", "AFL", "AIG", "AIZ", "AJG", "AKAM", "ALB", "ALGN", "ALL",
    "ALLE", "AMAT", "AMCR", "AMD", "AME", "AMGN", "AMP", "AMT", "AMZN", "ANET",
    "ANSS", "AON", "AOS", "APA", "APD", "APH", "APTV", "ARE", "ATO", "AVB",
    "AVGO", "AVY", "AWK", "AXP", "AZO", "BA", "BAC", "BALL", "BAX", "BBWI",
    "BBY", "BDX", "BEN", "BF.B", "BG", "BIIB", "BIO", "BK", "BKNG", "BKR",
    "BLDR", "BLK", "BMY", "BR", "BRK.B", "BRO", "BSX", "BWA", "BX", "BXP",
    "C", "CAG", "CAH", "CARR", "CAT", "CB", "CBOE", "CBRE", "CCI", "CCL",
    "CDAY", "CDNS", "CDW", "CE", "CEG", "CF", "CFG", "CHD", "CHRW", "CHTR",
    "CI", "CINF", "CL", "CLX", "CMA", "CMCSA", "CME", "CMG", "CMI", "CMS",
    "CNC", "CNP", "COF", "COO", "COP", "COR", "COST", "CPAY", "CPB", "CPRT",
    "CPT", "CRL", "CRM", "CSCO", "CSGP", "CSX", "CTAS", "CTLT", "CTRA", "CTSH",
    "CTVA", "CVS", "CVX", "CZR", "D", "DAL", "DD", "DE", "DFS", "DG",
    "DGX", "DHI", "DHR", "DIS", "DLR", "DLTR", "DOC", "DOV", "DOW", "DPZ",
    "DRI", "DTE", "DUK", "DVA", "DVN", "DXCM", "EA", "EBAY", "ECL", "ED",
    "EFX", "EG", "EIX", "EL", "ELV", "EMN", "EMR", "ENPH", "EOG", "EPAM",
    "EQIX", "EQR", "EQT", "ES", "ESS", "ETN", "ETR", "ETSY", "EVRG", "EW",
    "EXC", "EXPD", "EXPE", "EXR", "F", "FANG", "FAST", "FCX", "FDS", "FDX",
    "FE", "FFIV", "FI", "FICO", "FIS", "FITB", "FLT", "FMC", "FOX", "FOXA",
    "FRT", "FSLR", "FTNT", "FTV", "GD", "GDDY", "GE", "GEHC", "GEN", "GILD",
    "GIS", "GL", "GLW", "GM", "GNRC", "GOOG", "GOOGL", "GPC", "GPN", "GRMN",
    "GS", "GWW", "HAL", "HAS", "HBAN", "HCA", "HD", "HES", "HIG", "HII",
    "HLT", "HOLX", "HON", "HPE", "HPQ", "HRL", "HSIC", "HST", "HSY", "HUBB",
    "HUM", "HWM", "IBM", "ICE", "IDXX", "IEX", "IFF", "ILMN", "INCY", "INTC",
    "INTU", "INVH", "IP", "IPG", "IQV", "IR", "IRM", "ISRG", "IT", "ITW",
    "IVZ", "J", "JBHT", "JBL", "JCI", "JKHY", "JNJ", "JNPR", "JPM", "K",
    "KDP", "KEY", "KEYS", "KHC", "KIM", "KLAC", "KMB", "KMI", "KMX", "KO",
    "KR", "KVUE", "L", "LDOS", "LEN", "LH", "LHX", "LIN", "LKQ", "LLY",
    "LMT", "LNT", "LOW", "LRCX", "LULU", "LUV", "LVS", "LW", "LYB", "LYV",
    "MA", "MAA", "MAR", "MAS", "MCD", "MCHP", "MCK", "MCO", "MDLZ", "MDT",
    "MET", "META", "MGM", "MHK", "MKC", "MKTX", "MLM", "MMC", "MMM", "MNST",
    "MO", "MOH", "MOS", "MPC", "MPWR", "MRK", "MRNA", "MRO", "MS", "MSCI",
    "MSFT", "MSI", "MTB", "MTCH", "MTD", "MU", "NCLH", "NDAQ", "NDSN", "NEE",
    "NEM", "NFLX", "NI", "NKE", "NOC", "NOW", "NRG", "NSC", "NTAP", "NTRS",
    "NUE", "NVDA", "NVR", "NWS", "NWSA", "NXPI", "O", "ODFL", "OKE", "OMC",
    "ON", "ORCL", "ORLY", "OTIS", "OXY", "PANW", "PARA", "PAYC", "PAYX", "PCAR",
    "PCG", "PEG", "PEP", "PFE", "PFG", "PG", "PGR", "PH", "PHM", "PKG",
    "PLD", "PM", "PNC", "PNR", "PNW", "PODD", "POOL", "PPG", "PPL", "PRU",
    "PSA", "PSX", "PTC", "PWR", "PXD", "PYPL", "QCOM", "QRVO", "RCL", "REG",
    "REGN", "RF", "RJF", "RL", "RMD", "ROK", "ROL", "ROP", "ROST", "RSG",
    "RTX", "RVTY", "SBAC", "SBUX", "SCHW", "SHW", "SJM", "SLB", "SMCI", "SNA",
    "SNPS", "SO", "SOLV", "SPG", "SPGI", "SRE", "STE", "STLD", "STT", "STX",
    "STZ", "SWK", "SWKS", "SYF", "SYK", "SYY", "T", "TAP", "TDG", "TDY",
    "TECH", "TEL", "TER", "TFC", "TFX", "TGT", "TJX", "TMO", "TMUS", "TPR",
    "TRGP", "TRMB", "TROW", "TRV", "TSCO", "TSLA", "TSN", "TT", "TTWO", "TXN",
    "TXT", "TYL", "UAL", "UBER", "UDR", "UHS", "ULTA", "UNH", "UNP", "UPS",
    "URI", "USB", "V", "VFC", "VICI", "VLO", "VLTO", "VMC", "VRSK", "VRSN",
    "VRTX", "VST", "VTR", "VTRS", "VZ", "WAB", "WAT", "WBA", "WBD", "WDC",
    "WEC", "WELL", "WFC", "WM", "WMB", "WMT", "WRB", "WRK", "WST", "WTW",
    "WY", "WYNN", "XEL", "XOM", "XYL", "YUM", "ZBH", "ZBRA", "ZION", "ZTS"
]

# Sector mappings (simplified - in production would come from API)
SECTOR_MAP = {
    "Technology": ["AAPL", "MSFT", "NVDA", "AVGO", "CSCO", "ADBE", "CRM", "ORCL", "ACN", "INTC",
                   "AMD", "IBM", "QCOM", "TXN", "AMAT", "ADI", "LRCX", "MU", "KLAC", "SNPS",
                   "CDNS", "MCHP", "NXPI", "FTNT", "PANW", "NOW", "INTU", "ADSK", "ANSS", "KEYS"],
    "Healthcare": ["UNH", "JNJ", "LLY", "MRK", "ABBV", "PFE", "TMO", "ABT", "DHR", "BMY",
                   "AMGN", "MDT", "GILD", "VRTX", "ISRG", "REGN", "SYK", "BSX", "CI", "ELV",
                   "ZTS", "BDX", "HUM", "MCK", "HCA", "IDXX", "IQV", "DXCM", "BIIB", "MRNA"],
    "Financials": ["BRK.B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "SPGI", "BLK",
                   "SCHW", "C", "AXP", "PGR", "CB", "MMC", "ICE", "CME", "AON", "USB",
                   "PNC", "TFC", "AIG", "MET", "PRU", "TROW", "BK", "ALL", "COF", "AFL"],
    "Consumer Discretionary": ["AMZN", "TSLA", "HD", "MCD", "NKE", "LOW", "SBUX", "TJX", "BKNG", "CMG",
                                "ORLY", "AZO", "ROST", "MAR", "HLT", "GM", "F", "DHI", "LEN", "YUM"],
    "Communication Services": ["GOOGL", "GOOG", "META", "NFLX", "DIS", "CMCSA", "T", "VZ", "TMUS", "CHTR",
                                "EA", "TTWO", "WBD", "PARA", "OMC", "IPG", "FOX", "FOXA", "NWSA", "NWS"],
    "Industrials": ["CAT", "RTX", "HON", "UNP", "BA", "DE", "LMT", "UPS", "GE", "ETN",
                    "MMM", "EMR", "ITW", "PH", "NSC", "CSX", "WM", "FDX", "GD", "NOC"],
    "Consumer Staples": ["PG", "KO", "PEP", "COST", "WMT", "PM", "MDLZ", "MO", "CL", "EL",
                          "GIS", "KMB", "SYY", "KHC", "HSY", "K", "CAG", "CLX", "CHD", "MKC"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PXD", "PSX", "VLO", "OXY",
               "HAL", "DVN", "HES", "FANG", "BKR", "KMI", "WMB", "OKE", "TRGP", "MRO"],
    "Utilities": ["NEE", "DUK", "SO", "D", "AEP", "SRE", "EXC", "XEL", "PEG", "ED",
                  "EIX", "WEC", "ES", "AWK", "DTE", "ETR", "AEE", "CMS", "CNP", "FE"],
    "Real Estate": ["PLD", "AMT", "EQIX", "CCI", "PSA", "O", "SPG", "WELL", "DLR", "AVB",
                    "EQR", "VTR", "ARE", "MAA", "UDR", "ESS", "SBAC", "INVH", "CPT", "EXR"],
    "Materials": ["LIN", "APD", "SHW", "ECL", "FCX", "NUE", "VMC", "MLM", "NEM", "DOW",
                  "DD", "PPG", "CTVA", "ALB", "CF", "MOS", "IFF", "CE", "LYB", "EMN"]
}

# Invert sector map for lookup
TICKER_TO_SECTOR = {}
for sector, tickers in SECTOR_MAP.items():
    for ticker in tickers:
        TICKER_TO_SECTOR[ticker] = sector


class UniverseManager:
    """
    Manages the stock universe for analysis.
    Handles filtering and sector classification.
    """

    def __init__(self, polygon_client=None):
        self.polygon_client = polygon_client
        self._universe_cache = {}

    def get_sp500(self) -> List[str]:
        """Get S&P 500 constituent tickers."""
        return SP500_TICKERS.copy()

    def get_sector(self, ticker: str) -> Optional[str]:
        """Get sector classification for a ticker."""
        return TICKER_TO_SECTOR.get(ticker.upper())

    def get_sector_map(self) -> Dict[str, str]:
        """Get full ticker to sector mapping."""
        return TICKER_TO_SECTOR.copy()

    def get_tickers_by_sector(self, sector: str) -> List[str]:
        """Get all tickers in a specific sector."""
        return SECTOR_MAP.get(sector, []).copy()

    def filter_by_data_availability(
        self,
        tickers: List[str],
        financials_data: Dict[str, pd.DataFrame],
        min_periods: int = 4
    ) -> List[str]:
        """
        Filter tickers to those with sufficient financial data.

        Args:
            tickers: List of tickers to filter
            financials_data: Dictionary of financial DataFrames by ticker
            min_periods: Minimum number of periods required

        Returns:
            List of tickers with sufficient data
        """
        valid_tickers = []

        for ticker in tickers:
            df = financials_data.get(ticker, pd.DataFrame())
            if len(df) >= min_periods:
                # Check for key fields
                required_fields = ['revenue', 'net_income', 'total_assets', 'total_equity']
                has_data = all(
                    df[field].notna().any() if field in df.columns else False
                    for field in required_fields
                )
                if has_data:
                    valid_tickers.append(ticker)

        logger.info(f"Filtered universe: {len(valid_tickers)}/{len(tickers)} tickers have sufficient data")
        return valid_tickers

    def filter_by_market_cap(
        self,
        tickers: List[str],
        min_market_cap: float = 1e9,
        max_market_cap: float = None
    ) -> List[str]:
        """
        Filter tickers by market capitalization.

        Args:
            tickers: List of tickers to filter
            min_market_cap: Minimum market cap (default $1B)
            max_market_cap: Maximum market cap (optional)

        Returns:
            Filtered list of tickers
        """
        if self.polygon_client is None:
            logger.warning("No Polygon client provided, returning all tickers")
            return tickers

        valid_tickers = []

        for ticker in tickers:
            market_cap = self.polygon_client.get_market_cap(ticker)
            if market_cap is None:
                continue

            if market_cap >= min_market_cap:
                if max_market_cap is None or market_cap <= max_market_cap:
                    valid_tickers.append(ticker)

        return valid_tickers

    def exclude_sectors(
        self,
        tickers: List[str],
        sectors_to_exclude: List[str]
    ) -> List[str]:
        """
        Exclude tickers from specified sectors.

        Args:
            tickers: List of tickers to filter
            sectors_to_exclude: List of sector names to exclude

        Returns:
            Filtered list of tickers
        """
        return [
            ticker for ticker in tickers
            if self.get_sector(ticker) not in sectors_to_exclude
        ]

    def get_universe(
        self,
        universe_type: str = "sp500",
        exclude_financials: bool = False,
        exclude_utilities: bool = False,
        exclude_real_estate: bool = False
    ) -> List[str]:
        """
        Get filtered stock universe.

        Args:
            universe_type: Type of universe ("sp500")
            exclude_financials: Whether to exclude financial sector
            exclude_utilities: Whether to exclude utilities sector
            exclude_real_estate: Whether to exclude real estate sector

        Returns:
            List of ticker symbols
        """
        cache_key = (universe_type, exclude_financials, exclude_utilities, exclude_real_estate)

        if cache_key in self._universe_cache:
            return self._universe_cache[cache_key]

        if universe_type == "sp500":
            tickers = self.get_sp500()
        else:
            raise ValueError(f"Unknown universe type: {universe_type}")

        # Apply sector exclusions
        exclusions = []
        if exclude_financials:
            exclusions.append("Financials")
        if exclude_utilities:
            exclusions.append("Utilities")
        if exclude_real_estate:
            exclusions.append("Real Estate")

        if exclusions:
            tickers = self.exclude_sectors(tickers, exclusions)

        self._universe_cache[cache_key] = tickers
        return tickers

    def get_universe_summary(self, tickers: List[str] = None) -> pd.DataFrame:
        """
        Get summary statistics for the universe.

        Args:
            tickers: Optional list of tickers (defaults to S&P 500)

        Returns:
            DataFrame with sector breakdown
        """
        if tickers is None:
            tickers = self.get_sp500()

        sector_counts = {}
        for ticker in tickers:
            sector = self.get_sector(ticker) or "Unknown"
            sector_counts[sector] = sector_counts.get(sector, 0) + 1

        df = pd.DataFrame([
            {"sector": sector, "count": count, "pct": count / len(tickers) * 100}
            for sector, count in sorted(sector_counts.items())
        ])

        return df
