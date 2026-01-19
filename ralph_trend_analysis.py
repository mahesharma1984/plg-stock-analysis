#!/usr/bin/env python3
"""
RALPH Trend Analysis Module
High-signal trend detection and scoring for $RALPH whale tracking.

Features:
- SQLite time-series storage for historical analysis
- Multi-day accumulation/distribution phase detection
- Holder count tracking
- Liquidity depth monitoring over time
- Price correlation analysis
- Whale position velocity metrics
- Trend confidence scoring (BULLISH/BEARISH/NEUTRAL)
"""

import sqlite3
import json
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import requests

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()


# ============================================================
# ENUMS AND DATA STRUCTURES
# ============================================================

class TrendPhase(Enum):
    """Whale behavior phase classification."""
    ACCUMULATION = "ACCUMULATION"      # Multi-day buying pattern
    DISTRIBUTION = "DISTRIBUTION"       # Multi-day selling pattern
    CONSOLIDATION = "CONSOLIDATION"     # Sideways, no clear direction
    UNKNOWN = "UNKNOWN"                 # Insufficient data


class TrendSignal(Enum):
    """Overall market trend signal."""
    STRONG_BULLISH = "STRONG_BULLISH"   # High confidence buy signal
    BULLISH = "BULLISH"                  # Moderate buy signal
    NEUTRAL = "NEUTRAL"                  # No clear signal
    BEARISH = "BEARISH"                  # Moderate sell signal
    STRONG_BEARISH = "STRONG_BEARISH"   # High confidence sell signal


@dataclass
class MarketMetrics:
    """Current market state metrics."""
    timestamp: str
    price_usd: float = 0.0
    price_change_24h: float = 0.0
    volume_24h: float = 0.0
    liquidity_usd: float = 0.0
    liquidity_change_24h: float = 0.0
    holder_count: int = 0
    holder_change_24h: int = 0
    market_cap: float = 0.0


@dataclass
class WhaleTrendMetrics:
    """Whale-specific trend metrics for a single wallet."""
    wallet: str
    label: str
    current_balance: int
    balance_7d_ago: int
    balance_change_7d: int
    balance_change_7d_pct: float
    buy_count_7d: int
    sell_count_7d: int
    net_flow_7d: int  # positive = accumulating, negative = distributing
    velocity: float   # rate of change per day
    phase: TrendPhase


@dataclass
class TrendScore:
    """Aggregated trend confidence score."""
    signal: TrendSignal
    score: int  # -100 to +100
    confidence: float  # 0-1
    whale_phase: TrendPhase
    key_factors: List[str]
    timestamp: str


# ============================================================
# SQLITE DATABASE MANAGER
# ============================================================

class TrendDatabase:
    """SQLite database for storing historical trend data."""

    def __init__(self, db_path: str = "ralph_trends.db"):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize database tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Wallet balance history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wallet_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet TEXT NOT NULL,
                label TEXT NOT NULL,
                balance INTEGER NOT NULL,
                pct_supply REAL NOT NULL,
                tx_type TEXT,
                tx_amount INTEGER DEFAULT 0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(wallet, timestamp)
            )
        """)

        # Market metrics history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                price_usd REAL,
                volume_24h REAL,
                liquidity_usd REAL,
                holder_count INTEGER,
                market_cap REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Liquidity pool depth history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS liquidity_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pool_address TEXT NOT NULL,
                token_balance INTEGER NOT NULL,
                sol_balance INTEGER,
                depth_usd REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Trend scores history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trend_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal TEXT NOT NULL,
                score INTEGER NOT NULL,
                confidence REAL NOT NULL,
                whale_phase TEXT NOT NULL,
                key_factors TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Holder count snapshots
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS holder_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                holder_count INTEGER NOT NULL,
                top_10_pct REAL,
                top_50_pct REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for faster queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wallet_history_wallet ON wallet_history(wallet)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wallet_history_timestamp ON wallet_history(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_history_timestamp ON market_history(timestamp)")

        conn.commit()
        conn.close()

    def record_wallet_balance(self, wallet: str, label: str, balance: int,
                              pct_supply: float, tx_type: str = None, tx_amount: int = 0):
        """Record a wallet balance snapshot."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO wallet_history
            (wallet, label, balance, pct_supply, tx_type, tx_amount, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (wallet, label, balance, pct_supply, tx_type, tx_amount,
              datetime.utcnow().isoformat()))

        conn.commit()
        conn.close()

    def record_market_metrics(self, metrics: MarketMetrics):
        """Record market metrics snapshot."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO market_history
            (price_usd, volume_24h, liquidity_usd, holder_count, market_cap, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (metrics.price_usd, metrics.volume_24h, metrics.liquidity_usd,
              metrics.holder_count, metrics.market_cap, metrics.timestamp))

        conn.commit()
        conn.close()

    def record_liquidity(self, pool_address: str, token_balance: int,
                         sol_balance: int = 0, depth_usd: float = 0.0):
        """Record liquidity pool snapshot."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO liquidity_history
            (pool_address, token_balance, sol_balance, depth_usd, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (pool_address, token_balance, sol_balance, depth_usd,
              datetime.utcnow().isoformat()))

        conn.commit()
        conn.close()

    def record_holder_count(self, count: int, top_10_pct: float = 0.0, top_50_pct: float = 0.0):
        """Record holder count snapshot."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO holder_snapshots (holder_count, top_10_pct, top_50_pct, timestamp)
            VALUES (?, ?, ?, ?)
        """, (count, top_10_pct, top_50_pct, datetime.utcnow().isoformat()))

        conn.commit()
        conn.close()

    def record_trend_score(self, score: TrendScore):
        """Record a trend score calculation."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO trend_scores
            (signal, score, confidence, whale_phase, key_factors, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (score.signal.value, score.score, score.confidence,
              score.whale_phase.value, json.dumps(score.key_factors), score.timestamp))

        conn.commit()
        conn.close()

    def get_wallet_history(self, wallet: str, days: int = 7) -> List[Tuple]:
        """Get wallet balance history for N days."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        cursor.execute("""
            SELECT balance, pct_supply, tx_type, tx_amount, timestamp
            FROM wallet_history
            WHERE wallet = ? AND timestamp >= ?
            ORDER BY timestamp ASC
        """, (wallet, cutoff))

        results = cursor.fetchall()
        conn.close()
        return results

    def get_all_wallet_history(self, days: int = 7) -> Dict[str, List[Tuple]]:
        """Get history for all wallets."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        cursor.execute("""
            SELECT wallet, label, balance, pct_supply, tx_type, tx_amount, timestamp
            FROM wallet_history
            WHERE timestamp >= ?
            ORDER BY wallet, timestamp ASC
        """, (cutoff,))

        results = cursor.fetchall()
        conn.close()

        # Group by wallet
        history = {}
        for row in results:
            wallet = row[0]
            if wallet not in history:
                history[wallet] = []
            history[wallet].append(row[1:])  # Exclude wallet from tuple

        return history

    def get_liquidity_history(self, days: int = 7) -> List[Tuple]:
        """Get liquidity pool history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        cursor.execute("""
            SELECT token_balance, sol_balance, depth_usd, timestamp
            FROM liquidity_history
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
        """, (cutoff,))

        results = cursor.fetchall()
        conn.close()
        return results

    def get_holder_history(self, days: int = 7) -> List[Tuple]:
        """Get holder count history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        cursor.execute("""
            SELECT holder_count, top_10_pct, top_50_pct, timestamp
            FROM holder_snapshots
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
        """, (cutoff,))

        results = cursor.fetchall()
        conn.close()
        return results

    def get_market_history(self, days: int = 7) -> List[Tuple]:
        """Get market metrics history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        cursor.execute("""
            SELECT price_usd, volume_24h, liquidity_usd, holder_count, market_cap, timestamp
            FROM market_history
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
        """, (cutoff,))

        results = cursor.fetchall()
        conn.close()
        return results

    def get_trend_score_history(self, days: int = 7) -> List[TrendScore]:
        """Get trend score history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        cursor.execute("""
            SELECT signal, score, confidence, whale_phase, key_factors, timestamp
            FROM trend_scores
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
        """, (cutoff,))

        results = cursor.fetchall()
        conn.close()

        scores = []
        for row in results:
            scores.append(TrendScore(
                signal=TrendSignal(row[0]),
                score=row[1],
                confidence=row[2],
                whale_phase=TrendPhase(row[3]),
                key_factors=json.loads(row[4]) if row[4] else [],
                timestamp=row[5]
            ))

        return scores


# ============================================================
# DEX DATA FETCHER (Birdeye/Jupiter APIs)
# ============================================================

class DEXDataFetcher:
    """Fetches market data from DEX APIs."""

    BIRDEYE_BASE = "https://public-api.birdeye.so"
    JUPITER_PRICE_API = "https://price.jup.ag/v6/price"

    def __init__(self, token_address: str, api_key: str = None):
        self.token_address = token_address
        self.api_key = api_key or os.getenv("BIRDEYE_API_KEY", "")
        self.session = requests.Session()

    def get_token_price(self) -> Optional[Dict]:
        """Get current token price from Jupiter."""
        try:
            response = self.session.get(
                self.JUPITER_PRICE_API,
                params={"ids": self.token_address},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            if "data" in data and self.token_address in data["data"]:
                return data["data"][self.token_address]
            return None

        except Exception as e:
            console.print(f"[yellow]Jupiter API error: {e}[/yellow]")
            return None

    def get_token_overview(self) -> Optional[Dict]:
        """Get token overview from Birdeye (requires API key)."""
        if not self.api_key:
            return None

        try:
            headers = {"X-API-KEY": self.api_key}
            response = self.session.get(
                f"{self.BIRDEYE_BASE}/defi/token_overview",
                params={"address": self.token_address},
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            if data.get("success") and "data" in data:
                return data["data"]
            return None

        except Exception as e:
            console.print(f"[yellow]Birdeye API error: {e}[/yellow]")
            return None

    def get_holder_count(self) -> Optional[int]:
        """Get token holder count from Birdeye."""
        overview = self.get_token_overview()
        if overview:
            return overview.get("holder", 0)
        return None

    def get_market_metrics(self) -> MarketMetrics:
        """Get comprehensive market metrics."""
        metrics = MarketMetrics(timestamp=datetime.utcnow().isoformat())

        # Try Jupiter for price
        price_data = self.get_token_price()
        if price_data:
            metrics.price_usd = price_data.get("price", 0.0)

        # Try Birdeye for full overview
        overview = self.get_token_overview()
        if overview:
            metrics.price_usd = overview.get("price", metrics.price_usd)
            metrics.price_change_24h = overview.get("priceChange24hPercent", 0.0)
            metrics.volume_24h = overview.get("v24hUSD", 0.0)
            metrics.liquidity_usd = overview.get("liquidity", 0.0)
            metrics.holder_count = overview.get("holder", 0)
            metrics.market_cap = overview.get("mc", 0.0)

        return metrics


# ============================================================
# HOLDER COUNT TRACKER (Solana RPC)
# ============================================================

class HolderTracker:
    """Tracks token holder count via Solana RPC."""

    def __init__(self, rpc_url: str, token_address: str):
        self.rpc_url = rpc_url
        self.token_address = token_address
        self.session = requests.Session()

    def get_token_largest_accounts(self, limit: int = 20) -> Optional[List[Dict]]:
        """Get largest token accounts."""
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenLargestAccounts",
                "params": [self.token_address]
            }

            response = self.session.post(
                self.rpc_url,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()

            if "result" in result and "value" in result["result"]:
                return result["result"]["value"][:limit]
            return None

        except Exception as e:
            console.print(f"[yellow]RPC error getting largest accounts: {e}[/yellow]")
            return None

    def calculate_concentration(self, accounts: List[Dict], total_supply: int) -> Tuple[float, float]:
        """Calculate top 10 and top 50 holder concentration."""
        if not accounts:
            return 0.0, 0.0

        amounts = [int(acc.get("amount", 0)) for acc in accounts]

        top_10_total = sum(amounts[:10])
        top_50_total = sum(amounts[:50])

        top_10_pct = (top_10_total / total_supply * 100) if total_supply > 0 else 0.0
        top_50_pct = (top_50_total / total_supply * 100) if total_supply > 0 else 0.0

        return top_10_pct, top_50_pct


# ============================================================
# TREND ANALYZER
# ============================================================

class TrendAnalyzer:
    """Analyzes whale behavior patterns and calculates trend signals."""

    # Thresholds for phase detection
    ACCUMULATION_THRESHOLD = 2    # Net buys over sells for accumulation
    DISTRIBUTION_THRESHOLD = -2   # Net sells over buys for distribution
    VELOCITY_HIGH_THRESHOLD = 2.0  # High velocity (% change per day)

    def __init__(self, db: TrendDatabase, token_decimals: int = 9, total_supply: int = 1_000_000_000):
        self.db = db
        self.decimals = token_decimals
        self.total_supply = total_supply

    def analyze_wallet_trend(self, wallet: str, label: str, current_balance: int,
                              days: int = 7) -> WhaleTrendMetrics:
        """Analyze trend for a single wallet."""
        history = self.db.get_wallet_history(wallet, days)

        # Default values if no history
        if not history:
            return WhaleTrendMetrics(
                wallet=wallet,
                label=label,
                current_balance=current_balance,
                balance_7d_ago=current_balance,
                balance_change_7d=0,
                balance_change_7d_pct=0.0,
                buy_count_7d=0,
                sell_count_7d=0,
                net_flow_7d=0,
                velocity=0.0,
                phase=TrendPhase.UNKNOWN
            )

        # Get oldest balance in window
        balance_7d_ago = history[0][0]  # First record's balance
        balance_change = current_balance - balance_7d_ago

        # Calculate percentage change
        if balance_7d_ago > 0:
            balance_change_pct = (balance_change / balance_7d_ago) * 100
        else:
            balance_change_pct = 100.0 if balance_change > 0 else 0.0

        # Count buy/sell transactions
        buy_count = sum(1 for h in history if h[2] == "BUY")
        sell_count = sum(1 for h in history if h[2] == "SELL")

        # Calculate net flow (total bought - total sold)
        net_flow = 0
        for h in history:
            tx_type, tx_amount = h[2], h[3]
            if tx_type == "BUY":
                net_flow += tx_amount
            elif tx_type == "SELL":
                net_flow -= tx_amount

        # Calculate velocity (average daily change)
        velocity = balance_change_pct / days if days > 0 else 0.0

        # Determine phase
        phase = self._determine_phase(buy_count, sell_count, net_flow, velocity)

        return WhaleTrendMetrics(
            wallet=wallet,
            label=label,
            current_balance=current_balance,
            balance_7d_ago=balance_7d_ago,
            balance_change_7d=balance_change,
            balance_change_7d_pct=balance_change_pct,
            buy_count_7d=buy_count,
            sell_count_7d=sell_count,
            net_flow_7d=net_flow,
            velocity=velocity,
            phase=phase
        )

    def _determine_phase(self, buy_count: int, sell_count: int,
                         net_flow: int, velocity: float) -> TrendPhase:
        """Determine the whale's behavior phase."""
        net_tx = buy_count - sell_count

        if net_tx >= self.ACCUMULATION_THRESHOLD and net_flow > 0:
            return TrendPhase.ACCUMULATION
        elif net_tx <= self.DISTRIBUTION_THRESHOLD and net_flow < 0:
            return TrendPhase.DISTRIBUTION
        elif abs(velocity) < 0.5:  # Low velocity = consolidation
            return TrendPhase.CONSOLIDATION
        else:
            return TrendPhase.UNKNOWN

    def analyze_liquidity_trend(self, days: int = 7) -> Dict:
        """Analyze liquidity pool depth trend."""
        history = self.db.get_liquidity_history(days)

        if not history or len(history) < 2:
            return {
                "trend": "UNKNOWN",
                "change_pct": 0.0,
                "is_shrinking": False,
                "data_points": 0
            }

        first_depth = history[0][0]  # token_balance from first record
        last_depth = history[-1][0]  # token_balance from last record

        if first_depth > 0:
            change_pct = ((last_depth - first_depth) / first_depth) * 100
        else:
            change_pct = 0.0

        return {
            "trend": "GROWING" if change_pct > 5 else "SHRINKING" if change_pct < -5 else "STABLE",
            "change_pct": change_pct,
            "is_shrinking": change_pct < -5,
            "data_points": len(history)
        }

    def analyze_holder_trend(self, days: int = 7) -> Dict:
        """Analyze holder count trend."""
        history = self.db.get_holder_history(days)

        if not history or len(history) < 2:
            return {
                "trend": "UNKNOWN",
                "change": 0,
                "change_pct": 0.0,
                "is_declining": False,
                "current_count": 0
            }

        first_count = history[0][0]
        last_count = history[-1][0]
        change = last_count - first_count

        if first_count > 0:
            change_pct = (change / first_count) * 100
        else:
            change_pct = 0.0

        return {
            "trend": "GROWING" if change > 0 else "DECLINING" if change < 0 else "FLAT",
            "change": change,
            "change_pct": change_pct,
            "is_declining": change < 0,
            "current_count": last_count
        }

    def calculate_trend_score(self, wallet_metrics: List[WhaleTrendMetrics],
                               market_metrics: Optional[MarketMetrics] = None) -> TrendScore:
        """Calculate overall trend score from all signals."""
        score = 0
        factors = []

        # ============================================
        # WHALE BEHAVIOR SIGNALS (most important)
        # ============================================

        # Count whales in each phase
        accumulating = sum(1 for m in wallet_metrics if m.phase == TrendPhase.ACCUMULATION)
        distributing = sum(1 for m in wallet_metrics if m.phase == TrendPhase.DISTRIBUTION)

        # Phase scoring (-30 to +30)
        if accumulating >= 3:
            score += 30
            factors.append(f"{accumulating} whales accumulating")
        elif accumulating >= 2:
            score += 20
            factors.append(f"{accumulating} whales accumulating")
        elif accumulating == 1:
            score += 10
            factors.append("1 whale accumulating")

        if distributing >= 3:
            score -= 30
            factors.append(f"CRITICAL: {distributing} whales distributing")
        elif distributing >= 2:
            score -= 20
            factors.append(f"WARNING: {distributing} whales distributing")
        elif distributing == 1:
            score -= 10
            factors.append("1 whale distributing")

        # Net whale flow (-20 to +20)
        total_net_flow = sum(m.net_flow_7d for m in wallet_metrics)
        if total_net_flow > 0:
            score += min(20, int(total_net_flow / (10 ** self.decimals) / 1_000_000))  # +1 per 1M tokens
            factors.append(f"Net inflow: {total_net_flow / (10 ** self.decimals) / 1_000_000:.1f}M")
        elif total_net_flow < 0:
            score -= min(20, int(abs(total_net_flow) / (10 ** self.decimals) / 1_000_000))
            factors.append(f"Net outflow: {abs(total_net_flow) / (10 ** self.decimals) / 1_000_000:.1f}M")

        # Average velocity (-10 to +10)
        avg_velocity = sum(m.velocity for m in wallet_metrics) / len(wallet_metrics) if wallet_metrics else 0
        if avg_velocity > self.VELOCITY_HIGH_THRESHOLD:
            score += 10
            factors.append(f"High buy velocity: {avg_velocity:.1f}%/day")
        elif avg_velocity < -self.VELOCITY_HIGH_THRESHOLD:
            score -= 10
            factors.append(f"High sell velocity: {avg_velocity:.1f}%/day")

        # ============================================
        # LIQUIDITY SIGNALS
        # ============================================
        liquidity_trend = self.analyze_liquidity_trend()

        if liquidity_trend["is_shrinking"]:
            score -= 15
            factors.append(f"Liquidity shrinking: {liquidity_trend['change_pct']:.1f}%")
        elif liquidity_trend["trend"] == "GROWING":
            score += 10
            factors.append(f"Liquidity growing: {liquidity_trend['change_pct']:.1f}%")

        # ============================================
        # HOLDER COUNT SIGNALS
        # ============================================
        holder_trend = self.analyze_holder_trend()

        if holder_trend["is_declining"]:
            score -= 15
            factors.append(f"Holders declining: {holder_trend['change']}")
        elif holder_trend["trend"] == "GROWING":
            score += 15
            factors.append(f"Holders growing: +{holder_trend['change']}")

        # ============================================
        # MARKET METRICS (if available)
        # ============================================
        if market_metrics:
            # Volume signal
            if market_metrics.volume_24h > 1_000_000:
                score += 5
                factors.append(f"Strong volume: ${market_metrics.volume_24h/1e6:.1f}M")
            elif market_metrics.volume_24h < 100_000:
                score -= 5
                factors.append(f"Low volume: ${market_metrics.volume_24h/1e3:.0f}K")

            # Price trend correlation
            if market_metrics.price_change_24h > 10:
                if accumulating > distributing:
                    score += 5  # Whales buying into strength
                    factors.append("Whales buying into strength")
            elif market_metrics.price_change_24h < -10:
                if distributing > accumulating:
                    score -= 10  # Whales selling into weakness
                    factors.append("WARNING: Whales selling into weakness")

        # ============================================
        # DETERMINE SIGNAL AND CONFIDENCE
        # ============================================

        # Clamp score to -100 to +100
        score = max(-100, min(100, score))

        # Determine signal level
        if score >= 40:
            signal = TrendSignal.STRONG_BULLISH
        elif score >= 15:
            signal = TrendSignal.BULLISH
        elif score <= -40:
            signal = TrendSignal.STRONG_BEARISH
        elif score <= -15:
            signal = TrendSignal.BEARISH
        else:
            signal = TrendSignal.NEUTRAL

        # Calculate confidence (0-1) based on data quality
        data_points = len(wallet_metrics)
        has_liquidity_data = liquidity_trend["data_points"] > 0
        has_holder_data = holder_trend["current_count"] > 0
        has_market_data = market_metrics is not None and market_metrics.price_usd > 0

        confidence = 0.3  # Base confidence
        confidence += min(0.3, data_points * 0.03)  # Up to 0.3 for whale data
        confidence += 0.15 if has_liquidity_data else 0
        confidence += 0.15 if has_holder_data else 0
        confidence += 0.1 if has_market_data else 0
        confidence = min(1.0, confidence)

        # Determine dominant whale phase
        if accumulating > distributing:
            whale_phase = TrendPhase.ACCUMULATION
        elif distributing > accumulating:
            whale_phase = TrendPhase.DISTRIBUTION
        else:
            whale_phase = TrendPhase.CONSOLIDATION

        return TrendScore(
            signal=signal,
            score=score,
            confidence=confidence,
            whale_phase=whale_phase,
            key_factors=factors,
            timestamp=datetime.utcnow().isoformat()
        )


# ============================================================
# CLI FORMATTER FOR TRENDS
# ============================================================

class TrendFormatter:
    """Formats trend analysis output for CLI."""

    SIGNAL_COLORS = {
        TrendSignal.STRONG_BULLISH: "green bold",
        TrendSignal.BULLISH: "green",
        TrendSignal.NEUTRAL: "yellow",
        TrendSignal.BEARISH: "red",
        TrendSignal.STRONG_BEARISH: "red bold",
    }

    PHASE_COLORS = {
        TrendPhase.ACCUMULATION: "green",
        TrendPhase.DISTRIBUTION: "red",
        TrendPhase.CONSOLIDATION: "yellow",
        TrendPhase.UNKNOWN: "dim",
    }

    def __init__(self, token_decimals: int = 9):
        self.decimals = token_decimals

    def format_balance(self, raw_balance: int) -> str:
        """Format token balance for display."""
        balance = raw_balance / (10 ** self.decimals)
        if balance >= 1_000_000:
            return f"{balance/1_000_000:.1f}M"
        elif balance >= 1_000:
            return f"{balance/1_000:.1f}K"
        else:
            return f"{balance:.0f}"

    def print_trend_score(self, score: TrendScore):
        """Print the overall trend score."""
        color = self.SIGNAL_COLORS[score.signal]
        phase_color = self.PHASE_COLORS[score.whale_phase]

        # Score bar visualization
        bar_width = 40
        normalized = (score.score + 100) / 200  # 0 to 1
        filled = int(normalized * bar_width)
        bar = "[red]" + "-" * 20 + "[/red][yellow]|[/yellow][green]" + "-" * 20 + "[/green]"

        console.print()
        console.print(Panel.fit(
            f"[bold]TREND SIGNAL: [{color}]{score.signal.value}[/{color}][/bold]\n"
            f"Score: {score.score:+d}/100 | Confidence: {score.confidence*100:.0f}%\n"
            f"Whale Phase: [{phase_color}]{score.whale_phase.value}[/{phase_color}]",
            title="[bold cyan]RALPH Trend Analysis[/bold cyan]",
            border_style="cyan"
        ))

        # Key factors
        if score.key_factors:
            console.print("\n[bold]Key Factors:[/bold]")
            for factor in score.key_factors:
                if "CRITICAL" in factor or "WARNING" in factor:
                    console.print(f"  [red]! {factor}[/red]")
                elif any(x in factor.lower() for x in ["accumulating", "growing", "inflow", "strength"]):
                    console.print(f"  [green]+ {factor}[/green]")
                elif any(x in factor.lower() for x in ["distributing", "declining", "outflow", "weakness", "shrinking"]):
                    console.print(f"  [red]- {factor}[/red]")
                else:
                    console.print(f"  [dim]* {factor}[/dim]")

    def print_whale_metrics_table(self, metrics: List[WhaleTrendMetrics]):
        """Print whale trend metrics as a table."""
        table = Table(title="Whale 7-Day Trend Analysis", box=box.ROUNDED)

        table.add_column("Wallet", style="cyan", no_wrap=True)
        table.add_column("Balance", justify="right")
        table.add_column("7D Change", justify="right")
        table.add_column("Velocity", justify="right")
        table.add_column("Buys", justify="center")
        table.add_column("Sells", justify="center")
        table.add_column("Phase", justify="center")

        for m in metrics:
            balance_str = self.format_balance(m.current_balance)
            change_str = f"{m.balance_change_7d_pct:+.1f}%"
            velocity_str = f"{m.velocity:+.2f}%/d"

            # Color coding
            change_color = "green" if m.balance_change_7d_pct > 0 else "red" if m.balance_change_7d_pct < 0 else "white"
            phase_color = self.PHASE_COLORS[m.phase]

            table.add_row(
                m.label,
                balance_str,
                f"[{change_color}]{change_str}[/{change_color}]",
                f"[{change_color}]{velocity_str}[/{change_color}]",
                str(m.buy_count_7d),
                str(m.sell_count_7d),
                f"[{phase_color}]{m.phase.value}[/{phase_color}]"
            )

        console.print()
        console.print(table)

    def print_market_metrics(self, metrics: MarketMetrics):
        """Print market metrics panel."""
        price_color = "green" if metrics.price_change_24h > 0 else "red" if metrics.price_change_24h < 0 else "white"

        console.print()
        console.print(Panel.fit(
            f"[bold]Price:[/bold] ${metrics.price_usd:.6f} "
            f"[{price_color}]({metrics.price_change_24h:+.1f}% 24h)[/{price_color}]\n"
            f"[bold]Volume 24h:[/bold] ${metrics.volume_24h/1e6:.2f}M\n"
            f"[bold]Liquidity:[/bold] ${metrics.liquidity_usd/1e6:.2f}M\n"
            f"[bold]Holders:[/bold] {metrics.holder_count:,}\n"
            f"[bold]Market Cap:[/bold] ${metrics.market_cap/1e6:.2f}M",
            title="[bold]Market Metrics[/bold]",
            border_style="blue"
        ))

    def print_liquidity_trend(self, trend: Dict):
        """Print liquidity trend analysis."""
        trend_label = trend["trend"]
        color = "green" if trend_label == "GROWING" else "red" if trend_label == "SHRINKING" else "yellow"

        console.print()
        console.print(f"[bold]Liquidity Trend:[/bold] [{color}]{trend_label}[/{color}] "
                     f"({trend['change_pct']:+.1f}% over 7d)")

    def print_holder_trend(self, trend: Dict):
        """Print holder trend analysis."""
        trend_label = trend["trend"]
        color = "green" if trend_label == "GROWING" else "red" if trend_label == "DECLINING" else "yellow"

        console.print(f"[bold]Holder Trend:[/bold] [{color}]{trend_label}[/{color}] "
                     f"({trend['change']:+d} over 7d, now {trend['current_count']:,})")

    def print_decision_summary(self, score: TrendScore):
        """Print actionable decision summary."""
        console.print()
        console.print("[bold]Decision Summary:[/bold]")

        if score.signal == TrendSignal.STRONG_BULLISH:
            console.print("[green bold]SIGNAL: Consider adding to position on dips[/green bold]")
            console.print("[green]- Multiple whales accumulating[/green]")
            console.print("[green]- Strong holder growth and liquidity[/green]")
        elif score.signal == TrendSignal.BULLISH:
            console.print("[green]SIGNAL: Hold/maintain position[/green]")
            console.print("[dim]- Positive whale activity, monitor for changes[/dim]")
        elif score.signal == TrendSignal.NEUTRAL:
            console.print("[yellow]SIGNAL: Consolidation - wait for clearer direction[/yellow]")
            console.print("[dim]- No strong whale signal either way[/dim]")
        elif score.signal == TrendSignal.BEARISH:
            console.print("[red]SIGNAL: Consider reducing position[/red]")
            console.print("[dim]- Whale distribution signals detected[/dim]")
        elif score.signal == TrendSignal.STRONG_BEARISH:
            console.print("[red bold]SIGNAL: Consider exit - high dump risk[/red bold]")
            console.print("[red]- Multiple whales distributing[/red]")
            console.print("[red]- Declining liquidity and/or holders[/red]")

        console.print()


# ============================================================
# INTEGRATION WITH MAIN TRACKER
# ============================================================

class TrendTracker:
    """Main trend tracking class that integrates with RalphWhaleTracker."""

    def __init__(self, config_path: str = "ralph_config.yaml", db_path: str = "ralph_trends.db"):
        self.db = TrendDatabase(db_path)
        self.formatter = TrendFormatter()

        # Load config
        import yaml
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        self.token_address = config.get("token", {}).get("address", "")
        self.token_decimals = config.get("token", {}).get("decimals", 9)
        self.total_supply = config.get("token", {}).get("total_supply", 1_000_000_000)
        self.rpc_url = config.get("settings", {}).get("rpc_url", "")

        # Initialize components
        self.dex_fetcher = DEXDataFetcher(self.token_address)
        self.holder_tracker = HolderTracker(self.rpc_url, self.token_address)
        self.analyzer = TrendAnalyzer(self.db, self.token_decimals, self.total_supply)

        # Store wallet info
        self.wallets = {w["address"]: w for w in config.get("wallets", [])}

    def record_snapshot(self, wallet_states: Dict):
        """Record current wallet states to trend database."""
        for addr, state in wallet_states.items():
            # Handle both dict and dataclass states
            if hasattr(state, 'balance_ralph'):
                balance = state.balance_ralph
                label = state.label
                pct = state.pct_supply
                tx_type = state.last_tx_type
                tx_amount = state.last_tx_amount
            else:
                balance = state.get('balance_ralph', 0)
                label = state.get('label', 'unknown')
                pct = state.get('pct_supply', 0.0)
                tx_type = state.get('last_tx_type')
                tx_amount = state.get('last_tx_amount', 0)

            self.db.record_wallet_balance(
                wallet=addr,
                label=label,
                balance=balance,
                pct_supply=pct,
                tx_type=tx_type,
                tx_amount=tx_amount
            )

    def record_liquidity(self, pool_address: str, token_balance: int,
                         sol_balance: int = 0, depth_usd: float = 0.0):
        """Record liquidity pool snapshot."""
        self.db.record_liquidity(pool_address, token_balance, sol_balance, depth_usd)

    def fetch_and_record_market_data(self) -> Optional[MarketMetrics]:
        """Fetch current market data and record it."""
        metrics = self.dex_fetcher.get_market_metrics()

        if metrics.price_usd > 0 or metrics.holder_count > 0:
            self.db.record_market_metrics(metrics)

            # Also record holder count separately for trend tracking
            if metrics.holder_count > 0:
                # Get concentration data
                largest = self.holder_tracker.get_token_largest_accounts()
                if largest:
                    top_10, top_50 = self.holder_tracker.calculate_concentration(
                        largest, self.total_supply * (10 ** self.token_decimals)
                    )
                    self.db.record_holder_count(metrics.holder_count, top_10, top_50)
                else:
                    self.db.record_holder_count(metrics.holder_count)

            return metrics

        return None

    def run_analysis(self, wallet_states: Dict) -> TrendScore:
        """Run full trend analysis and return score."""
        # Record current states first
        self.record_snapshot(wallet_states)

        # Fetch market data
        market_metrics = self.fetch_and_record_market_data()

        # Analyze each whale
        whale_metrics = []
        for addr, state in wallet_states.items():
            if hasattr(state, 'is_pool') and state.is_pool:
                continue  # Skip pool for whale analysis
            if isinstance(state, dict) and state.get('is_pool'):
                continue

            if hasattr(state, 'balance_ralph'):
                balance = state.balance_ralph
                label = state.label
            else:
                balance = state.get('balance_ralph', 0)
                label = state.get('label', 'unknown')

            metrics = self.analyzer.analyze_wallet_trend(addr, label, balance)
            whale_metrics.append(metrics)

        # Calculate overall trend score
        score = self.analyzer.calculate_trend_score(whale_metrics, market_metrics)

        # Record the score
        self.db.record_trend_score(score)

        return score, whale_metrics, market_metrics

    def show_trend_report(self, wallet_states: Dict):
        """Generate and display full trend report."""
        console.print("[cyan]Analyzing trends...[/cyan]")

        score, whale_metrics, market_metrics = self.run_analysis(wallet_states)

        # Print trend score
        self.formatter.print_trend_score(score)

        # Print whale metrics table
        if whale_metrics:
            self.formatter.print_whale_metrics_table(whale_metrics)

        # Print market metrics
        if market_metrics and market_metrics.price_usd > 0:
            self.formatter.print_market_metrics(market_metrics)

        # Print liquidity and holder trends
        liquidity_trend = self.analyzer.analyze_liquidity_trend()
        holder_trend = self.analyzer.analyze_holder_trend()

        self.formatter.print_liquidity_trend(liquidity_trend)
        self.formatter.print_holder_trend(holder_trend)

        # Print decision summary
        self.formatter.print_decision_summary(score)

        return score

    def get_trend_history(self, days: int = 7) -> List[TrendScore]:
        """Get historical trend scores."""
        return self.db.get_trend_score_history(days)


# ============================================================
# CLI ENTRY POINT
# ============================================================

def main():
    """Standalone trend analysis CLI."""
    import argparse

    parser = argparse.ArgumentParser(
        description="RALPH Trend Analyzer - High-signal whale trend detection"
    )

    parser.add_argument(
        '--config', '-c',
        default='ralph_config.yaml',
        help='Path to configuration file'
    )

    parser.add_argument(
        '--db', '-d',
        default='ralph_trends.db',
        help='Path to trends database'
    )

    parser.add_argument(
        '--history',
        type=int,
        metavar='DAYS',
        help='Show trend score history for N days'
    )

    args = parser.parse_args()

    # Initialize tracker
    tracker = TrendTracker(args.config, args.db)

    if args.history:
        # Show history
        scores = tracker.get_trend_history(args.history)
        console.print(f"\n[bold]Trend Score History ({args.history} days)[/bold]\n")

        for score in scores[:20]:  # Show last 20
            color = tracker.formatter.SIGNAL_COLORS[score.signal]
            console.print(f"{score.timestamp[:16]} | [{color}]{score.signal.value:15}[/{color}] | "
                         f"Score: {score.score:+4d} | Confidence: {score.confidence*100:.0f}%")
    else:
        console.print("[yellow]Use with ralph_tracker.py for full trend analysis[/yellow]")
        console.print("Run: python ralph_tracker.py --trends")


if __name__ == "__main__":
    main()
