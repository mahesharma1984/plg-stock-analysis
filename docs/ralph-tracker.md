# RALPH Whale Tracker Documentation

A Python CLI tool for tracking whale wallet activity on the $RALPH token (Solana).

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Signals](#signals)
- [Architecture](#architecture)
- [Troubleshooting](#troubleshooting)

---

## Overview

The RALPH Whale Tracker monitors large holder ("whale") wallets for the Ralph Wiggum ($RALPH) token on Solana. It detects buy/sell activity, CEX transfers, and liquidity changes to help inform trading decisions.

### Token Information

| Property | Value |
|----------|-------|
| **Name** | Ralph Wiggum |
| **Symbol** | $RALPH |
| **Contract** | `CxWPdDBqxVo3fnTMRTvNuSrd4gkp78udSrFvkVDBAGS` |
| **Chain** | Solana |
| **DEX** | Meteora |
| **Pool** | `DbyK8gEiXwNeh2zFW2Lo1svuQ1WkHAeQyNDsRaKQ6BHf` |

### Key Features

- Real-time polling of whale wallet balances
- Signal detection for buys, sells, and CEX transfers
- Liquidity pool depth monitoring
- Coordinated activity detection (accumulation/distribution)
- Color-coded CLI output
- Persistent state and logging

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements_ralph.txt

# 2. Take a snapshot of current balances
python ralph_tracker.py --snapshot

# 3. Start continuous tracking
python ralph_tracker.py
```

---

## Installation

### Prerequisites

- Python 3.8+
- pip

### Steps

1. **Install dependencies:**

   ```bash
   pip install -r requirements_ralph.txt
   ```

2. **Configure wallets** (optional):

   Edit `ralph_config.yaml` to add/update wallet addresses. Get full addresses from [Solscan Holders](https://solscan.io/token/CxWPdDBqxVo3fnTMRTvNuSrd4gkp78udSrFvkVDBAGS#holders).

3. **Set up API keys** (optional):

   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

### Dependencies

| Package | Purpose |
|---------|---------|
| `solana` | Solana RPC client |
| `solders` | Solana data structures |
| `requests` | HTTP requests |
| `rich` | CLI formatting and colors |
| `pyyaml` | Configuration parsing |
| `python-dotenv` | Environment variables |
| `base58` | Address encoding |

---

## Usage

### Basic Commands

```bash
# Start continuous polling (default: 60s interval)
python ralph_tracker.py

# Use custom configuration file
python ralph_tracker.py --config /path/to/config.yaml

# Override poll interval (seconds)
python ralph_tracker.py --interval 30

# One-time snapshot of current balances
python ralph_tracker.py --snapshot

# View historical signals
python ralph_tracker.py --history 24h
python ralph_tracker.py --history 7d

# Add a new wallet to track
python ralph_tracker.py --add-wallet "whale_4" "FULL_WALLET_ADDRESS"

# Enable verbose output
python ralph_tracker.py --verbose
```

### Command Reference

| Flag | Short | Description |
|------|-------|-------------|
| `--config` | `-c` | Path to config file (default: `ralph_config.yaml`) |
| `--interval` | `-i` | Poll interval in seconds |
| `--snapshot` | `-s` | Show current balances only, no polling |
| `--history` | | Show historical signals (e.g., `24h`, `12h`, `1d`) |
| `--add-wallet` | | Add wallet: `--add-wallet LABEL ADDRESS` |
| `--verbose` | `-v` | Enable verbose output |

### Output Examples

**Normal polling output:**
```
[2026-01-19 14:33:15] + whale_1: 93.3M RALPH (9.33%) - No change
[2026-01-19 14:33:15] + whale_2: 45.8M RALPH (4.58%) - No change
[2026-01-19 14:33:15] + liquidity_pool: 150.0M RALPH depth - No change
------------------------------------------------------------
```

**Buy signal:**
```
------------------------------------------------------------
[2026-01-19 14:45:22] WHALE_BUY | whale_1 bought 2.1M RALPH (+2.25%)
         New balance: 95.4M (9.54% of supply)
         Tx: 4xK9f... view on Solscan
```

**Sell signal:**
```
------------------------------------------------------------
[2026-01-19 16:12:08] WHALE_SELL | whale_2 sold 5M RALPH (-10.9%)
         New balance: 40.8M (4.08% of supply)
         Tx: 7yH2a... view on Solscan
```

**CEX transfer (critical):**
```
------------------------------------------------------------
[2026-01-19 18:30:45] CRITICAL: WHALE_TO_CEX | whale_3 transferred 10M RALPH to binance
         Potential dump incoming - consider exit
```

---

## Configuration

See [Configuration Guide](./configuration.md) for full details.

### Config File Location

By default, the tracker looks for `ralph_config.yaml` in the current directory.

### Minimal Config

```yaml
token:
  address: "CxWPdDBqxVo3fnTMRTvNuSrd4gkp78udSrFvkVDBAGS"
  symbol: "RALPH"
  total_supply: 1000000000

wallets:
  - label: "whale_1"
    address: "FULL_WALLET_ADDRESS_HERE"

settings:
  poll_interval_seconds: 60
```

---

## Signals

See [Signals Reference](./signals.md) for full details.

### Signal Types

| Signal | Meaning | Severity | Color |
|--------|---------|----------|-------|
| `WHALE_BUY` | Tracked wallet balance increased | INFO | Green |
| `WHALE_SELL` | Tracked wallet balance decreased | WARNING | Red |
| `WHALE_TO_CEX` | Transfer to known CEX wallet | CRITICAL | Red |
| `LIQUIDITY_DROP` | Pool depth dropped >10% | WARNING | Red |
| `LIQUIDITY_ADD` | Pool depth increased >10% | INFO | Green |
| `ACCUMULATION` | 2+ whales buying same day | INFO | Green |
| `DISTRIBUTION` | 2+ whales selling same day | WARNING | Red |

### Trading Implications

| Signal | Implication |
|--------|-------------|
| `WHALE_BUY` | Bullish - whale accumulating |
| `WHALE_SELL` | Bearish - whale reducing position |
| `WHALE_TO_CEX` | Very bearish - likely preparing to dump |
| `LIQUIDITY_DROP` | Bearish - reduced exit liquidity |
| `ACCUMULATION` | Very bullish - coordinated buying |
| `DISTRIBUTION` | Very bearish - coordinated selling |

---

## Architecture

### Components

```
ralph_tracker.py
    |
    +-- TrackerConfig       # Configuration management
    |
    +-- SolanaRPCClient     # Blockchain interaction
    |       |
    |       +-- getTokenAccountsByOwner
    |       +-- getSignaturesForAddress
    |       +-- getTransaction
    |
    +-- SignalDetector      # Signal detection logic
    |       |
    |       +-- detect_balance_change
    |       +-- detect_cex_transfer
    |       +-- detect_liquidity_change
    |       +-- detect_coordinated_activity
    |
    +-- TrackerLogger       # File logging
    |
    +-- CLIFormatter        # Terminal output
    |
    +-- RalphWhaleTracker   # Main orchestrator
```

### Data Flow

1. **Poll**: Fetch token balances via Solana RPC
2. **Compare**: Check against previous state
3. **Detect**: Identify signals based on thresholds
4. **Log**: Write to log file
5. **Display**: Output to CLI
6. **Persist**: Save state to JSON

### Files

| File | Purpose |
|------|---------|
| `ralph_config.yaml` | Configuration |
| `ralph_tracker_state.json` | Persisted wallet state |
| `ralph_tracker.log` | Event log |

---

## Troubleshooting

### RPC Errors

**Problem:** `RPC request failed` errors

**Solution:**
1. Check internet connection
2. The tracker will auto-rotate to backup RPC URLs
3. Add more RPC URLs to `settings.rpc_backup_urls` in config

### Zero Balances

**Problem:** All wallets showing 0 balance

**Solution:**
1. Verify wallet addresses are correct (full addresses, not truncated)
2. Verify token contract address is correct
3. Check wallet actually holds the token on [Solscan](https://solscan.io)

### No Signals Detected

**Problem:** Tracking runs but no signals appear

**Solution:**
1. Signals only appear when balance changes exceed `alert_threshold_pct`
2. Lower the threshold in config (e.g., from `1.0` to `0.5`)
3. Run `--snapshot` to verify current balances

### Missing Dependencies

**Problem:** `ModuleNotFoundError`

**Solution:**
```bash
pip install -r requirements_ralph.txt
```

### Permission Denied

**Problem:** Cannot write log/state files

**Solution:**
```bash
chmod 755 .
touch ralph_tracker.log ralph_tracker_state.json
```

---

## Resources

- [Solscan Token Page](https://solscan.io/token/CxWPdDBqxVo3fnTMRTvNuSrd4gkp78udSrFvkVDBAGS)
- [DEX Screener](https://dexscreener.com/solana/dbyk8geixwneh2zfw2lo1svuq1wkhaeqyndsrakq6bhf)
- [Solana RPC Docs](https://docs.solana.com/api/http)
- [solana-py Documentation](https://michaelhly.github.io/solana-py/)
