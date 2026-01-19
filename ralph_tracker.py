#!/usr/bin/env python3
"""
RALPH Whale Tracker CLI
Track whale wallet activity for the $RALPH token on Solana.
Logs buy/sell signals to help inform trading decisions.

Token: Ralph Wiggum ($RALPH)
Contract: CxWPdDBqxVo3fnTMRTvNuSrd4gkp78udSrFvkVDBAGS
Chain: Solana
DEX: Meteora

Features:
- Real-time whale wallet monitoring
- Buy/sell signal detection
- CEX transfer alerts
- Multi-day trend analysis
- Holder count tracking
- Liquidity depth monitoring
- Trend confidence scoring
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import base58
import requests
import yaml
from dotenv import load_dotenv

# Rich for CLI formatting
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

# Trend analysis module
try:
    from ralph_trend_analysis import TrendTracker, TrendScore, TrendSignal
    TREND_ANALYSIS_AVAILABLE = True
except ImportError:
    TREND_ANALYSIS_AVAILABLE = False

# Load environment variables
load_dotenv()

# Initialize Rich console
console = Console()

# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class WalletState:
    """Tracks state of a single wallet."""
    wallet: str
    label: str
    balance_ralph: int = 0
    balance_ralph_prev: int = 0
    pct_supply: float = 0.0
    last_tx_type: str = ""  # BUY | SELL | TRANSFER_IN | TRANSFER_OUT | NO_CHANGE
    last_tx_amount: int = 0
    last_tx_time: str = ""
    last_tx_sig: str = ""
    is_pool: bool = False
    alert_threshold_pct: float = 1.0
    notes: str = ""


@dataclass
class Signal:
    """Represents a detected signal/event."""
    signal_type: str
    wallet_label: str
    wallet_address: str
    amount: int = 0
    pct_change: float = 0.0
    new_balance: int = 0
    new_pct_supply: float = 0.0
    tx_signature: str = ""
    target_label: str = ""  # For CEX transfers
    timestamp: str = ""
    severity: str = "INFO"  # INFO, WARNING, CRITICAL


@dataclass
class TrackerConfig:
    """Configuration for the tracker."""
    token_address: str = ""
    token_symbol: str = "RALPH"
    token_decimals: int = 6
    total_supply: int = 1_000_000_000
    wallets: List[Dict] = field(default_factory=list)
    cex_wallets: List[Dict] = field(default_factory=list)
    poll_interval: int = 60
    log_file: str = "ralph_tracker.log"
    state_file: str = "ralph_tracker_state.json"
    rpc_url: str = "https://api.mainnet-beta.solana.com"
    rpc_backup_urls: List[str] = field(default_factory=list)
    max_retries: int = 3
    retry_delay: int = 2
    request_timeout: int = 30


# ============================================================
# CONFIGURATION LOADING
# ============================================================

def load_config(config_path: str) -> TrackerConfig:
    """Load configuration from YAML file."""
    config = TrackerConfig()

    if not os.path.exists(config_path):
        console.print(f"[yellow]Config file not found: {config_path}[/yellow]")
        console.print("[yellow]Using default configuration.[/yellow]")
        return config

    with open(config_path, 'r') as f:
        data = yaml.safe_load(f)

    # Token config
    token = data.get('token', {})
    config.token_address = token.get('address', config.token_address)
    config.token_symbol = token.get('symbol', config.token_symbol)
    config.token_decimals = token.get('decimals', config.token_decimals)
    config.total_supply = token.get('total_supply', config.total_supply)

    # Wallets
    config.wallets = data.get('wallets', [])
    config.cex_wallets = data.get('cex_wallets', [])

    # Settings
    settings = data.get('settings', {})
    config.poll_interval = settings.get('poll_interval_seconds', config.poll_interval)
    config.log_file = settings.get('log_file', config.log_file)
    config.state_file = settings.get('state_file', config.state_file)
    config.rpc_url = settings.get('rpc_url', config.rpc_url)
    config.rpc_backup_urls = settings.get('rpc_backup_urls', [])
    config.max_retries = settings.get('max_retries', config.max_retries)
    config.retry_delay = settings.get('retry_delay_seconds', config.retry_delay)
    config.request_timeout = settings.get('request_timeout_seconds', config.request_timeout)

    return config


def save_state(state: Dict[str, WalletState], state_file: str):
    """Save wallet states to JSON file."""
    data = {addr: asdict(ws) for addr, ws in state.items()}
    with open(state_file, 'w') as f:
        json.dump(data, f, indent=2)


def load_state(state_file: str) -> Dict[str, WalletState]:
    """Load wallet states from JSON file."""
    if not os.path.exists(state_file):
        return {}

    with open(state_file, 'r') as f:
        data = json.load(f)

    states = {}
    for addr, ws_data in data.items():
        states[addr] = WalletState(**ws_data)
    return states


# ============================================================
# SOLANA RPC CLIENT
# ============================================================

class SolanaRPCClient:
    """Client for interacting with Solana RPC."""

    def __init__(self, config: TrackerConfig):
        self.config = config
        self.rpc_urls = [config.rpc_url] + config.rpc_backup_urls
        self.current_rpc_index = 0
        self.session = requests.Session()

    def _get_rpc_url(self) -> str:
        """Get current RPC URL."""
        return self.rpc_urls[self.current_rpc_index]

    def _rotate_rpc(self):
        """Rotate to next RPC URL."""
        self.current_rpc_index = (self.current_rpc_index + 1) % len(self.rpc_urls)
        console.print(f"[yellow]Rotating to RPC: {self._get_rpc_url()}[/yellow]")

    def _rpc_call(self, method: str, params: List[Any]) -> Optional[Dict]:
        """Make an RPC call with retry logic."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }

        for attempt in range(self.config.max_retries):
            try:
                response = self.session.post(
                    self._get_rpc_url(),
                    json=payload,
                    timeout=self.config.request_timeout,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                result = response.json()

                if "error" in result:
                    console.print(f"[red]RPC error: {result['error']}[/red]")
                    return None

                return result.get("result")

            except requests.exceptions.RequestException as e:
                console.print(f"[yellow]RPC request failed (attempt {attempt + 1}): {e}[/yellow]")
                if attempt < self.config.max_retries - 1:
                    self._rotate_rpc()
                    time.sleep(self.config.retry_delay * (2 ** attempt))
                else:
                    console.print(f"[red]All RPC attempts failed for {method}[/red]")
                    return None

        return None

    def get_token_accounts_by_owner(self, owner: str, token_mint: str) -> Optional[List[Dict]]:
        """Get token accounts owned by an address for a specific token."""
        params = [
            owner,
            {"mint": token_mint},
            {"encoding": "jsonParsed"}
        ]
        result = self._rpc_call("getTokenAccountsByOwner", params)
        if result and "value" in result:
            return result["value"]
        return None

    def get_balance(self, address: str) -> Optional[int]:
        """Get SOL balance for an address (in lamports)."""
        result = self._rpc_call("getBalance", [address])
        if result and "value" in result:
            return result["value"]
        return None

    def get_token_balance(self, owner: str, token_mint: str) -> Optional[int]:
        """Get token balance for a wallet address."""
        accounts = self.get_token_accounts_by_owner(owner, token_mint)
        if not accounts:
            return 0

        total_balance = 0
        for account in accounts:
            try:
                parsed = account.get("account", {}).get("data", {}).get("parsed", {})
                info = parsed.get("info", {})
                token_amount = info.get("tokenAmount", {})
                amount = int(token_amount.get("amount", 0))
                total_balance += amount
            except (KeyError, ValueError, TypeError):
                continue

        return total_balance

    def get_signatures_for_address(self, address: str, limit: int = 10) -> Optional[List[Dict]]:
        """Get recent transaction signatures for an address."""
        params = [address, {"limit": limit}]
        return self._rpc_call("getSignaturesForAddress", params)

    def get_transaction(self, signature: str) -> Optional[Dict]:
        """Get transaction details by signature."""
        params = [
            signature,
            {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}
        ]
        return self._rpc_call("getTransaction", params)


# ============================================================
# SIGNAL DETECTION
# ============================================================

class SignalDetector:
    """Detects and categorizes whale activity signals."""

    def __init__(self, config: TrackerConfig, cex_addresses: set):
        self.config = config
        self.cex_addresses = cex_addresses
        self.daily_signals: List[Signal] = []

    def detect_balance_change(
        self,
        wallet_state: WalletState,
        new_balance: int,
        recent_sigs: Optional[List[Dict]] = None
    ) -> Optional[Signal]:
        """Detect and classify a balance change."""

        prev_balance = wallet_state.balance_ralph
        balance_diff = new_balance - prev_balance

        if balance_diff == 0:
            return None

        # Calculate percentage change
        if prev_balance > 0:
            pct_change = (balance_diff / prev_balance) * 100
        else:
            pct_change = 100.0 if balance_diff > 0 else 0.0

        # Check if change exceeds threshold
        if abs(pct_change) < wallet_state.alert_threshold_pct:
            return None

        # Calculate new supply percentage
        decimals = self.config.token_decimals
        display_balance = new_balance / (10 ** decimals)
        new_pct_supply = (display_balance / self.config.total_supply) * 100

        # Determine signal type
        if balance_diff > 0:
            signal_type = "WHALE_BUY"
            tx_type = "BUY"
            severity = "INFO"
        else:
            signal_type = "WHALE_SELL"
            tx_type = "SELL"
            severity = "WARNING"

        # Get latest transaction signature
        tx_sig = ""
        if recent_sigs and len(recent_sigs) > 0:
            tx_sig = recent_sigs[0].get("signature", "")

        signal = Signal(
            signal_type=signal_type,
            wallet_label=wallet_state.label,
            wallet_address=wallet_state.wallet,
            amount=abs(balance_diff),
            pct_change=pct_change,
            new_balance=new_balance,
            new_pct_supply=new_pct_supply,
            tx_signature=tx_sig,
            timestamp=datetime.utcnow().isoformat() + "Z",
            severity=severity
        )

        self.daily_signals.append(signal)
        return signal

    def detect_cex_transfer(
        self,
        wallet_state: WalletState,
        tx_data: Dict
    ) -> Optional[Signal]:
        """Detect transfer to CEX wallet."""
        # Parse transaction to check for transfers to CEX addresses
        # This is a simplified check - full implementation would parse
        # the transaction instructions more thoroughly

        try:
            meta = tx_data.get("meta", {})
            post_balances = meta.get("postTokenBalances", [])
            pre_balances = meta.get("preTokenBalances", [])

            for post in post_balances:
                owner = post.get("owner", "")
                if owner in self.cex_addresses:
                    # Found transfer to CEX
                    cex_label = self._get_cex_label(owner)
                    return Signal(
                        signal_type="WHALE_TO_CEX",
                        wallet_label=wallet_state.label,
                        wallet_address=wallet_state.wallet,
                        target_label=cex_label,
                        tx_signature=tx_data.get("transaction", {}).get("signatures", [""])[0],
                        timestamp=datetime.utcnow().isoformat() + "Z",
                        severity="CRITICAL"
                    )
        except (KeyError, TypeError):
            pass

        return None

    def _get_cex_label(self, address: str) -> str:
        """Get label for CEX address."""
        for cex in self.config.cex_wallets:
            if cex.get("address") == address:
                return cex.get("label", "unknown_cex")
        return "unknown_cex"

    def detect_liquidity_change(
        self,
        pool_state: WalletState,
        new_balance: int
    ) -> Optional[Signal]:
        """Detect significant liquidity pool changes."""

        prev_balance = pool_state.balance_ralph
        if prev_balance == 0:
            return None

        pct_change = ((new_balance - prev_balance) / prev_balance) * 100

        if abs(pct_change) < pool_state.alert_threshold_pct:
            return None

        if pct_change < 0:
            signal_type = "LIQUIDITY_DROP"
            severity = "WARNING"
        else:
            signal_type = "LIQUIDITY_ADD"
            severity = "INFO"

        return Signal(
            signal_type=signal_type,
            wallet_label=pool_state.label,
            wallet_address=pool_state.wallet,
            amount=abs(new_balance - prev_balance),
            pct_change=pct_change,
            new_balance=new_balance,
            timestamp=datetime.utcnow().isoformat() + "Z",
            severity=severity
        )

    def detect_coordinated_activity(self) -> List[Signal]:
        """Detect coordinated whale activity (accumulation/distribution)."""
        signals = []

        # Check signals from today
        today = datetime.utcnow().date()
        today_buys = []
        today_sells = []

        for sig in self.daily_signals:
            try:
                sig_date = datetime.fromisoformat(sig.timestamp.rstrip('Z')).date()
                if sig_date == today:
                    if sig.signal_type == "WHALE_BUY":
                        today_buys.append(sig)
                    elif sig.signal_type == "WHALE_SELL":
                        today_sells.append(sig)
            except ValueError:
                continue

        # Check for accumulation (2+ whales buying)
        unique_buyers = set(s.wallet_label for s in today_buys)
        if len(unique_buyers) >= 2:
            signals.append(Signal(
                signal_type="ACCUMULATION",
                wallet_label=", ".join(unique_buyers),
                wallet_address="",
                timestamp=datetime.utcnow().isoformat() + "Z",
                severity="INFO"
            ))

        # Check for distribution (2+ whales selling)
        unique_sellers = set(s.wallet_label for s in today_sells)
        if len(unique_sellers) >= 2:
            signals.append(Signal(
                signal_type="DISTRIBUTION",
                wallet_label=", ".join(unique_sellers),
                wallet_address="",
                timestamp=datetime.utcnow().isoformat() + "Z",
                severity="WARNING"
            ))

        return signals

    def reset_daily_signals(self):
        """Reset daily signal tracking."""
        self.daily_signals = []


# ============================================================
# LOGGING
# ============================================================

class TrackerLogger:
    """Handles logging to file and console."""

    def __init__(self, log_file: str):
        self.log_file = log_file
        self.log_dir = Path(log_file).parent
        if self.log_dir and not self.log_dir.exists():
            self.log_dir.mkdir(parents=True, exist_ok=True)

    def log_poll(self, wallet_state: WalletState, change_type: str = "NO_CHANGE"):
        """Log a poll result."""
        decimals = 6  # RALPH decimals
        display_balance = wallet_state.balance_ralph / (10 ** decimals)

        line = (
            f"{datetime.utcnow().isoformat()}Z|INFO|POLL|"
            f"{wallet_state.label}|{wallet_state.balance_ralph}|"
            f"{wallet_state.pct_supply:.2f}|{change_type}"
        )
        self._write_log(line)

    def log_signal(self, signal: Signal):
        """Log a signal/event."""
        line = (
            f"{signal.timestamp}|{signal.severity}|{signal.signal_type}|"
            f"{signal.wallet_label}|{signal.new_balance}|"
            f"{signal.new_pct_supply:.2f}|{signal.amount:+d}|{signal.tx_signature}"
        )
        self._write_log(line)

    def log_cex_transfer(self, signal: Signal):
        """Log CEX transfer."""
        line = (
            f"{signal.timestamp}|{signal.severity}|{signal.signal_type}|"
            f"{signal.wallet_label}|{signal.target_label}|"
            f"{signal.amount}|{signal.tx_signature}"
        )
        self._write_log(line)

    def _write_log(self, line: str):
        """Write line to log file."""
        with open(self.log_file, 'a') as f:
            f.write(line + "\n")

    def read_history(self, hours: int = 24) -> List[str]:
        """Read log entries from the last N hours."""
        if not os.path.exists(self.log_file):
            return []

        cutoff = datetime.utcnow() - timedelta(hours=hours)
        entries = []

        with open(self.log_file, 'r') as f:
            for line in f:
                try:
                    ts_str = line.split('|')[0]
                    ts = datetime.fromisoformat(ts_str.rstrip('Z'))
                    if ts >= cutoff:
                        entries.append(line.strip())
                except (IndexError, ValueError):
                    continue

        return entries


# ============================================================
# CLI OUTPUT FORMATTING
# ============================================================

class CLIFormatter:
    """Formats output for the CLI."""

    SIGNAL_COLORS = {
        "WHALE_BUY": "green",
        "WHALE_SELL": "red",
        "WHALE_TO_CEX": "red bold",
        "LIQUIDITY_DROP": "red",
        "LIQUIDITY_ADD": "green",
        "ACCUMULATION": "green",
        "DISTRIBUTION": "red",
        "NO_CHANGE": "white",
    }

    SIGNAL_ICONS = {
        "WHALE_BUY": "[green]:heavy_check_mark:[/green]",
        "WHALE_SELL": "[red]:warning:[/red]",
        "WHALE_TO_CEX": "[red]:rotating_light:[/red]",
        "LIQUIDITY_DROP": "[red]:chart_decreasing:[/red]",
        "LIQUIDITY_ADD": "[green]:chart_increasing:[/green]",
        "ACCUMULATION": "[green]:thumbs_up:[/green]",
        "DISTRIBUTION": "[red]:thumbs_down:[/red]",
        "NO_CHANGE": "[white]:heavy_check_mark:[/white]",
    }

    def __init__(self, token_decimals: int = 6):
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

    def format_timestamp(self) -> str:
        """Format current timestamp for display."""
        return datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")

    def print_header(self, wallet_count: int, poll_interval: int):
        """Print startup header."""
        console.print()
        console.print(Panel.fit(
            f"[bold cyan]RALPH Whale Tracker Started[/bold cyan]\n"
            f"Tracking {wallet_count} wallets | Poll interval: {poll_interval}s",
            border_style="cyan"
        ))
        console.print("-" * 60)

    def print_wallet_status(self, wallet_state: WalletState, change_type: str = "NO_CHANGE"):
        """Print wallet status line."""
        ts = self.format_timestamp()
        balance_str = self.format_balance(wallet_state.balance_ralph)
        pct_str = f"{wallet_state.pct_supply:.2f}%"

        color = self.SIGNAL_COLORS.get(change_type, "white")
        icon = "+" if change_type == "NO_CHANGE" else ("!" if "SELL" in change_type else "+")

        if wallet_state.is_pool:
            console.print(
                f"{ts} [green]+[/green] [bold]{wallet_state.label}[/bold]: "
                f"{balance_str} RALPH depth - [{color}]No change[/{color}]"
            )
        else:
            console.print(
                f"{ts} [green]+[/green] [bold]{wallet_state.label}[/bold]: "
                f"{balance_str} RALPH ({pct_str}) - [{color}]No change[/{color}]"
            )

    def print_signal(self, signal: Signal):
        """Print a detected signal."""
        ts = self.format_timestamp()
        color = self.SIGNAL_COLORS.get(signal.signal_type, "white")

        # Format amount for display
        amount_str = self.format_balance(signal.amount)

        console.print("-" * 60)

        if signal.signal_type == "WHALE_BUY":
            console.print(
                f"{ts} [green bold]WHALE_BUY[/green bold] | "
                f"{signal.wallet_label} bought {amount_str} RALPH "
                f"([green]+{signal.pct_change:.2f}%[/green])"
            )
        elif signal.signal_type == "WHALE_SELL":
            console.print(
                f"{ts} [red bold]WHALE_SELL[/red bold] | "
                f"{signal.wallet_label} sold {amount_str} RALPH "
                f"([red]{signal.pct_change:.2f}%[/red])"
            )
        elif signal.signal_type == "WHALE_TO_CEX":
            console.print(
                f"{ts} [red bold]CRITICAL: WHALE_TO_CEX[/red bold] | "
                f"{signal.wallet_label} transferred {amount_str} RALPH to {signal.target_label}"
            )
            console.print(f"         [red bold]Potential dump incoming - consider exit[/red bold]")
        elif signal.signal_type == "LIQUIDITY_DROP":
            console.print(
                f"{ts} [red bold]LIQUIDITY_DROP[/red bold] | "
                f"Pool depth decreased by {abs(signal.pct_change):.1f}%"
            )
        elif signal.signal_type == "LIQUIDITY_ADD":
            console.print(
                f"{ts} [green bold]LIQUIDITY_ADD[/green bold] | "
                f"Pool depth increased by {signal.pct_change:.1f}%"
            )
        elif signal.signal_type == "ACCUMULATION":
            console.print(
                f"{ts} [green bold]ACCUMULATION[/green bold] | "
                f"Multiple whales buying: {signal.wallet_label}"
            )
        elif signal.signal_type == "DISTRIBUTION":
            console.print(
                f"{ts} [red bold]DISTRIBUTION[/red bold] | "
                f"Multiple whales selling: {signal.wallet_label}"
            )

        # Print additional details
        if signal.new_balance > 0:
            balance_str = self.format_balance(signal.new_balance)
            console.print(
                f"         New balance: {balance_str} ({signal.new_pct_supply:.2f}% of supply)"
            )

        if signal.tx_signature:
            short_sig = signal.tx_signature[:8] + "..."
            console.print(
                f"         Tx: {short_sig} "
                f"[link=https://solscan.io/tx/{signal.tx_signature}]view on Solscan[/link]"
            )

    def print_snapshot_table(self, wallet_states: Dict[str, WalletState]):
        """Print a snapshot table of all wallets."""
        table = Table(title="RALPH Wallet Snapshot", box=box.ROUNDED)

        table.add_column("Label", style="cyan", no_wrap=True)
        table.add_column("Balance", justify="right", style="green")
        table.add_column("% Supply", justify="right")
        table.add_column("Last Change", justify="center")
        table.add_column("Notes", style="dim")

        for ws in wallet_states.values():
            balance_str = self.format_balance(ws.balance_ralph)
            pct_str = f"{ws.pct_supply:.2f}%"
            last_change = ws.last_tx_type if ws.last_tx_type else "-"

            change_style = "green" if "BUY" in last_change else "red" if "SELL" in last_change else "white"

            table.add_row(
                ws.label,
                f"{balance_str} RALPH",
                pct_str,
                f"[{change_style}]{last_change}[/{change_style}]",
                ws.notes[:30] + "..." if len(ws.notes) > 30 else ws.notes
            )

        console.print()
        console.print(table)
        console.print()

    def print_history(self, entries: List[str]):
        """Print historical log entries."""
        console.print()
        console.print(Panel.fit(
            f"[bold]Historical Signals[/bold] ({len(entries)} entries)",
            border_style="blue"
        ))

        for entry in entries:
            parts = entry.split('|')
            if len(parts) >= 3:
                ts = parts[0]
                severity = parts[1]
                signal_type = parts[2]

                color = self.SIGNAL_COLORS.get(signal_type, "white")
                console.print(f"  [{color}]{ts} | {signal_type} | {' | '.join(parts[3:])}[/{color}]")


# ============================================================
# MAIN TRACKER CLASS
# ============================================================

class RalphWhaleTracker:
    """Main whale tracker class."""

    def __init__(self, config_path: str = "ralph_config.yaml"):
        self.config = load_config(config_path)
        self.config_path = config_path
        self.rpc = SolanaRPCClient(self.config)
        self.formatter = CLIFormatter(self.config.token_decimals)
        self.logger = TrackerLogger(self.config.log_file)

        # Build CEX address set
        self.cex_addresses = set(w.get("address", "") for w in self.config.cex_wallets)
        self.detector = SignalDetector(self.config, self.cex_addresses)

        # Load or initialize wallet states
        self.wallet_states = load_state(self.config.state_file)
        self._initialize_wallet_states()

        # Initialize trend tracker if available
        self.trend_tracker = None
        if TREND_ANALYSIS_AVAILABLE:
            try:
                self.trend_tracker = TrendTracker(config_path)
                console.print("[dim]Trend analysis enabled[/dim]")
            except Exception as e:
                console.print(f"[yellow]Trend analysis unavailable: {e}[/yellow]")

    def _initialize_wallet_states(self):
        """Initialize wallet states from config."""
        for wallet_cfg in self.config.wallets:
            addr = wallet_cfg.get("address", "")
            if addr and addr not in self.wallet_states:
                self.wallet_states[addr] = WalletState(
                    wallet=addr,
                    label=wallet_cfg.get("label", "unknown"),
                    is_pool=wallet_cfg.get("is_pool", False),
                    alert_threshold_pct=wallet_cfg.get("alert_threshold_pct", 1.0),
                    notes=wallet_cfg.get("notes", "")
                )

    def fetch_balances(self) -> Dict[str, int]:
        """Fetch current RALPH balances for all tracked wallets."""
        balances = {}

        for addr in self.wallet_states:
            balance = self.rpc.get_token_balance(addr, self.config.token_address)
            if balance is not None:
                balances[addr] = balance
            else:
                console.print(f"[yellow]Failed to fetch balance for {addr}[/yellow]")
                balances[addr] = self.wallet_states[addr].balance_ralph

        return balances

    def update_and_detect(self, new_balances: Dict[str, int]) -> List[Signal]:
        """Update wallet states and detect signals."""
        signals = []

        for addr, new_balance in new_balances.items():
            if addr not in self.wallet_states:
                continue

            ws = self.wallet_states[addr]

            # Get recent transactions for context
            recent_sigs = self.rpc.get_signatures_for_address(addr, limit=5)

            # Detect balance change
            if ws.is_pool:
                signal = self.detector.detect_liquidity_change(ws, new_balance)
            else:
                signal = self.detector.detect_balance_change(ws, new_balance, recent_sigs)

            if signal:
                signals.append(signal)
                self.logger.log_signal(signal)
            else:
                self.logger.log_poll(ws)

            # Update state
            ws.balance_ralph_prev = ws.balance_ralph
            ws.balance_ralph = new_balance
            ws.pct_supply = (new_balance / (10 ** self.config.token_decimals)) / self.config.total_supply * 100

            if signal:
                ws.last_tx_type = "BUY" if "BUY" in signal.signal_type else "SELL" if "SELL" in signal.signal_type else ""
                ws.last_tx_amount = signal.amount
                ws.last_tx_time = signal.timestamp
                ws.last_tx_sig = signal.tx_signature

        # Check for coordinated activity
        coordinated = self.detector.detect_coordinated_activity()
        signals.extend(coordinated)

        # Save state
        save_state(self.wallet_states, self.config.state_file)

        return signals

    def run_snapshot(self):
        """Run a single snapshot and display current balances."""
        console.print("[cyan]Fetching current wallet balances...[/cyan]")

        balances = self.fetch_balances()

        # Update states
        for addr, balance in balances.items():
            if addr in self.wallet_states:
                ws = self.wallet_states[addr]
                ws.balance_ralph = balance
                ws.pct_supply = (balance / (10 ** self.config.token_decimals)) / self.config.total_supply * 100

        self.formatter.print_snapshot_table(self.wallet_states)
        save_state(self.wallet_states, self.config.state_file)

    def run_polling(self, record_trends: bool = True):
        """Run continuous polling loop."""
        self.formatter.print_header(
            len(self.wallet_states),
            self.config.poll_interval
        )

        poll_count = 0
        trend_record_interval = 5  # Record trend data every N polls

        try:
            while True:
                poll_count += 1

                # Fetch current balances
                new_balances = self.fetch_balances()

                # Update and detect signals
                signals = self.update_and_detect(new_balances)

                # Print status for each wallet
                for addr, ws in self.wallet_states.items():
                    if any(s.wallet_address == addr for s in signals):
                        continue  # Signal already printed
                    self.formatter.print_wallet_status(ws)

                # Print any detected signals
                for signal in signals:
                    self.formatter.print_signal(signal)

                # Record trend data periodically
                if record_trends and poll_count % trend_record_interval == 0:
                    self.record_trend_data()
                    self.show_quick_trend()

                console.print("-" * 60)

                # Wait for next poll
                time.sleep(self.config.poll_interval)

        except KeyboardInterrupt:
            console.print("\n[yellow]Tracker stopped by user.[/yellow]")
            # Final trend data recording
            if record_trends:
                self.record_trend_data()
            save_state(self.wallet_states, self.config.state_file)

    def show_history(self, hours: int = 24):
        """Show historical signals."""
        entries = self.logger.read_history(hours)
        self.formatter.print_history(entries)

    def add_wallet(self, label: str, address: str, threshold: float = 1.0):
        """Add a new wallet to track."""
        if address in self.wallet_states:
            console.print(f"[yellow]Wallet {address} already being tracked.[/yellow]")
            return

        self.wallet_states[address] = WalletState(
            wallet=address,
            label=label,
            alert_threshold_pct=threshold
        )

        # Fetch initial balance
        balance = self.rpc.get_token_balance(address, self.config.token_address)
        if balance is not None:
            self.wallet_states[address].balance_ralph = balance
            self.wallet_states[address].pct_supply = (
                (balance / (10 ** self.config.token_decimals)) / self.config.total_supply * 100
            )

        save_state(self.wallet_states, self.config.state_file)
        console.print(f"[green]Added wallet: {label} ({address})[/green]")

    def run_trend_analysis(self):
        """Run full trend analysis and display report."""
        if not self.trend_tracker:
            console.print("[red]Trend analysis not available. Check ralph_trend_analysis.py[/red]")
            return None

        # Make sure we have current balances
        console.print("[cyan]Fetching current wallet balances...[/cyan]")
        balances = self.fetch_balances()

        # Update states
        for addr, balance in balances.items():
            if addr in self.wallet_states:
                ws = self.wallet_states[addr]
                ws.balance_ralph = balance
                ws.pct_supply = (balance / (10 ** self.config.token_decimals)) / self.config.total_supply * 100

        save_state(self.wallet_states, self.config.state_file)

        # Run trend analysis
        return self.trend_tracker.show_trend_report(self.wallet_states)

    def record_trend_data(self):
        """Record current state to trend database (called during polling)."""
        if not self.trend_tracker:
            return

        try:
            # Record wallet snapshots
            self.trend_tracker.record_snapshot(self.wallet_states)

            # Record liquidity for pool wallets
            for addr, ws in self.wallet_states.items():
                if ws.is_pool:
                    self.trend_tracker.record_liquidity(addr, ws.balance_ralph)

        except Exception as e:
            console.print(f"[dim]Trend recording error: {e}[/dim]")

    def show_trend_history(self, days: int = 7):
        """Show historical trend scores."""
        if not self.trend_tracker:
            console.print("[red]Trend analysis not available.[/red]")
            return

        scores = self.trend_tracker.get_trend_history(days)

        if not scores:
            console.print("[yellow]No trend history available yet.[/yellow]")
            console.print("[dim]Run trend analysis or polling to build history.[/dim]")
            return

        console.print()
        console.print(Panel.fit(
            f"[bold]Trend Score History ({days} days)[/bold]\n"
            f"Showing {len(scores)} recorded scores",
            border_style="blue"
        ))
        console.print()

        table = Table(box=box.SIMPLE)
        table.add_column("Timestamp", style="dim")
        table.add_column("Signal", justify="center")
        table.add_column("Score", justify="right")
        table.add_column("Confidence", justify="right")
        table.add_column("Whale Phase", justify="center")

        SIGNAL_COLORS = {
            "STRONG_BULLISH": "green bold",
            "BULLISH": "green",
            "NEUTRAL": "yellow",
            "BEARISH": "red",
            "STRONG_BEARISH": "red bold",
        }

        PHASE_COLORS = {
            "ACCUMULATION": "green",
            "DISTRIBUTION": "red",
            "CONSOLIDATION": "yellow",
            "UNKNOWN": "dim",
        }

        for score in scores[:20]:  # Show last 20
            signal_color = SIGNAL_COLORS.get(score.signal.value, "white")
            phase_color = PHASE_COLORS.get(score.whale_phase.value, "white")

            table.add_row(
                score.timestamp[:16],
                f"[{signal_color}]{score.signal.value}[/{signal_color}]",
                f"{score.score:+d}",
                f"{score.confidence*100:.0f}%",
                f"[{phase_color}]{score.whale_phase.value}[/{phase_color}]"
            )

        console.print(table)
        console.print()

    def show_quick_trend(self):
        """Show quick trend summary without full analysis."""
        if not self.trend_tracker:
            console.print("[dim]Trend analysis not available[/dim]")
            return

        scores = self.trend_tracker.get_trend_history(1)
        if scores:
            latest = scores[0]
            SIGNAL_COLORS = {
                "STRONG_BULLISH": "green bold",
                "BULLISH": "green",
                "NEUTRAL": "yellow",
                "BEARISH": "red",
                "STRONG_BEARISH": "red bold",
            }
            color = SIGNAL_COLORS.get(latest.signal.value, "white")
            console.print(f"[dim]Latest trend:[/dim] [{color}]{latest.signal.value}[/{color}] "
                         f"(Score: {latest.score:+d}, {latest.confidence*100:.0f}% confidence)")


# ============================================================
# CLI ENTRY POINT
# ============================================================

def parse_history_arg(value: str) -> int:
    """Parse history argument (e.g., '24h', '12h', '1d')."""
    value = value.lower().strip()
    if value.endswith('h'):
        return int(value[:-1])
    elif value.endswith('d'):
        return int(value[:-1]) * 24
    else:
        return int(value)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="RALPH Whale Tracker - Track whale wallet activity for $RALPH on Solana",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ralph_tracker.py                    # Start tracking with trend analysis
  python ralph_tracker.py --config my.yaml   # Use custom config
  python ralph_tracker.py --interval 30      # Poll every 30 seconds
  python ralph_tracker.py --snapshot         # Show current balances only
  python ralph_tracker.py --history 24h      # Show signals from last 24 hours
  python ralph_tracker.py --add-wallet "whale_4" "ABC123..."

Trend Analysis:
  python ralph_tracker.py --trends           # Run full trend analysis
  python ralph_tracker.py --trend-history 7  # Show trend history for 7 days

Trend signals:
  STRONG_BULLISH  - Multiple whales accumulating, strong holder growth
  BULLISH         - Positive whale activity
  NEUTRAL         - Consolidation, no clear direction
  BEARISH         - Whale distribution signals
  STRONG_BEARISH  - Multiple whales distributing, declining liquidity
        """
    )

    parser.add_argument(
        '--config', '-c',
        default='ralph_config.yaml',
        help='Path to configuration file (default: ralph_config.yaml)'
    )

    parser.add_argument(
        '--interval', '-i',
        type=int,
        help='Override poll interval in seconds'
    )

    parser.add_argument(
        '--snapshot', '-s',
        action='store_true',
        help='Show current balances only (no polling)'
    )

    parser.add_argument(
        '--history',
        metavar='PERIOD',
        help='Show historical signals (e.g., 24h, 12h, 1d)'
    )

    parser.add_argument(
        '--add-wallet',
        nargs=2,
        metavar=('LABEL', 'ADDRESS'),
        help='Add a new wallet to track'
    )

    parser.add_argument(
        '--trends', '-t',
        action='store_true',
        help='Run full trend analysis (7-day whale behavior, holder count, liquidity)'
    )

    parser.add_argument(
        '--trend-history',
        type=int,
        metavar='DAYS',
        help='Show trend score history for N days'
    )

    parser.add_argument(
        '--no-trend-recording',
        action='store_true',
        help='Disable trend data recording during polling'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )

    args = parser.parse_args()

    # Initialize tracker
    tracker = RalphWhaleTracker(args.config)

    # Override poll interval if specified
    if args.interval:
        tracker.config.poll_interval = args.interval

    # Handle different modes
    if args.add_wallet:
        label, address = args.add_wallet
        tracker.add_wallet(label, address)
    elif args.history:
        hours = parse_history_arg(args.history)
        tracker.show_history(hours)
    elif args.trends:
        tracker.run_trend_analysis()
    elif args.trend_history:
        tracker.show_trend_history(args.trend_history)
    elif args.snapshot:
        tracker.run_snapshot()
    else:
        record_trends = not args.no_trend_recording
        tracker.run_polling(record_trends=record_trends)


if __name__ == "__main__":
    main()
