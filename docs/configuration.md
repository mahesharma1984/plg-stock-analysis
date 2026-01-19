# Configuration Guide

Complete reference for configuring the RALPH Whale Tracker.

## Config File

The tracker uses YAML configuration. By default, it looks for `ralph_config.yaml` in the current directory.

```bash
# Use default config
python ralph_tracker.py

# Use custom config
python ralph_tracker.py --config /path/to/my_config.yaml
```

---

## Full Configuration Reference

```yaml
# ===========================================
# TOKEN CONFIGURATION
# ===========================================
token:
  # Token mint address (required)
  address: "CxWPdDBqxVo3fnTMRTvNuSrd4gkp78udSrFvkVDBAGS"

  # Token symbol for display
  symbol: "RALPH"

  # Token decimals (RALPH uses 6)
  decimals: 6

  # Total supply (used for % calculations)
  total_supply: 1000000000

# ===========================================
# TRACKED WALLETS
# ===========================================
wallets:
  # Whale wallet example
  - label: "whale_1"                    # Display name
    address: "B93svZ..."                # Full Solana address (44 chars)
    notes: "Top holder ~9.33%"          # Optional notes
    alert_threshold_pct: 1.0            # Alert if balance changes >1%

  # Another whale
  - label: "whale_2"
    address: "5tFsLP..."
    notes: "#2 holder ~4.58%"
    alert_threshold_pct: 1.0

  # Liquidity pool (special handling)
  - label: "liquidity_pool"
    address: "DbyK8g..."
    notes: "Meteora primary pool"
    alert_threshold_pct: 10.0           # Higher threshold for pools
    is_pool: true                       # Marks as liquidity pool

# ===========================================
# CEX WALLETS (for dump detection)
# ===========================================
cex_wallets:
  - label: "binance"
    address: "5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9"

  - label: "coinbase"
    address: "H8sMJSCQxfKiFTCfDR3DUMLPwcRbM61LGFJ8N4dK3WjS"

  - label: "kraken"
    address: "KRAKEN_ADDRESS_HERE"

# ===========================================
# TRACKER SETTINGS
# ===========================================
settings:
  # How often to poll balances (seconds)
  poll_interval_seconds: 60

  # Log file path
  log_file: "ralph_tracker.log"

  # State file path (persists between runs)
  state_file: "ralph_tracker_state.json"

  # Primary Solana RPC URL
  rpc_url: "https://api.mainnet-beta.solana.com"

  # Backup RPC URLs (auto-rotates on failure)
  rpc_backup_urls:
    - "https://solana-mainnet.g.alchemy.com/v2/demo"
    - "https://rpc.ankr.com/solana"

  # Max retry attempts for RPC calls
  max_retries: 3

  # Delay between retries (seconds, uses exponential backoff)
  retry_delay_seconds: 2

  # Request timeout (seconds)
  request_timeout_seconds: 30
```

---

## Section Details

### Token Configuration

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `address` | string | Yes | SPL token mint address |
| `symbol` | string | No | Token symbol for display (default: "RALPH") |
| `decimals` | int | No | Token decimals (default: 6) |
| `total_supply` | int | No | Total supply for % calculations (default: 1B) |

### Wallet Configuration

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `label` | string | Yes | Display name (e.g., "whale_1") |
| `address` | string | Yes | Full Solana wallet address (44 chars) |
| `notes` | string | No | Optional description |
| `alert_threshold_pct` | float | No | Min % change to trigger alert (default: 1.0) |
| `is_pool` | bool | No | Mark as liquidity pool (default: false) |

### CEX Wallet Configuration

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `label` | string | Yes | CEX name (e.g., "binance") |
| `address` | string | Yes | Known CEX deposit address |

### Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `poll_interval_seconds` | int | 60 | Polling frequency |
| `log_file` | string | ralph_tracker.log | Log file path |
| `state_file` | string | ralph_tracker_state.json | State persistence file |
| `rpc_url` | string | mainnet-beta | Primary RPC endpoint |
| `rpc_backup_urls` | list | [] | Backup RPC endpoints |
| `max_retries` | int | 3 | Max RPC retry attempts |
| `retry_delay_seconds` | int | 2 | Base retry delay |
| `request_timeout_seconds` | int | 30 | RPC request timeout |

---

## Environment Variables

Optional API keys can be set via `.env` file:

```bash
# Copy template
cp .env.example .env
```

**.env file:**
```bash
# Custom RPC URL (overrides config)
SOLANA_RPC_URL=https://your-rpc-provider.com

# Solscan API key (for enriched data)
SOLSCAN_API_KEY=your_key_here

# Birdeye API key (for price data - future)
BIRDEYE_API_KEY=your_key_here
```

---

## Finding Wallet Addresses

### From Solscan

1. Go to the [RALPH token holders page](https://solscan.io/token/CxWPdDBqxVo3fnTMRTvNuSrd4gkp78udSrFvkVDBAGS#holders)
2. Click on a wallet address to view full address
3. Copy the complete 44-character address

### From DEX Screener

1. Go to the [RALPH pool on DEX Screener](https://dexscreener.com/solana/dbyk8geixwneh2zfw2lo1svuq1wkhaeqyndsrakq6bhf)
2. Click "Holders" or "Top Traders"
3. Copy wallet addresses

---

## RPC Providers

### Free Options

| Provider | URL | Rate Limit |
|----------|-----|------------|
| Solana Public | `https://api.mainnet-beta.solana.com` | Low |
| Ankr | `https://rpc.ankr.com/solana` | Moderate |
| Alchemy (demo) | `https://solana-mainnet.g.alchemy.com/v2/demo` | Low |

### Paid Options (Higher Limits)

| Provider | Notes |
|----------|-------|
| [Helius](https://helius.xyz) | Good free tier |
| [QuickNode](https://quicknode.com) | Reliable |
| [Alchemy](https://alchemy.com) | Enterprise grade |
| [Triton](https://triton.one) | Solana-focused |

**Recommendation:** For production use, get a dedicated RPC endpoint from Helius or QuickNode.

---

## Alert Thresholds

The `alert_threshold_pct` determines when signals are triggered:

| Threshold | Use Case |
|-----------|----------|
| 0.1% | Very sensitive - many alerts |
| 0.5% | Sensitive - catches small moves |
| 1.0% | Default - significant moves only |
| 2.0% | Conservative - large moves only |
| 5.0% | Very conservative |
| 10.0% | Recommended for liquidity pools |

**Example:** With `alert_threshold_pct: 1.0`, a whale holding 100M tokens must buy/sell at least 1M tokens to trigger an alert.

---

## Example Configurations

### Minimal (Single Whale)

```yaml
token:
  address: "CxWPdDBqxVo3fnTMRTvNuSrd4gkp78udSrFvkVDBAGS"

wallets:
  - label: "top_holder"
    address: "FULL_ADDRESS_HERE"

settings:
  poll_interval_seconds: 60
```

### Production (Multiple Whales + Pool)

```yaml
token:
  address: "CxWPdDBqxVo3fnTMRTvNuSrd4gkp78udSrFvkVDBAGS"
  symbol: "RALPH"
  decimals: 6
  total_supply: 1000000000

wallets:
  - label: "whale_1"
    address: "B93svZLmpNPdpBrNa6r1BbJphj2E7hTDx4fAfnHbKMUj"
    alert_threshold_pct: 0.5
  - label: "whale_2"
    address: "5tFsLPyhWGJRdnHzTqKZWJfpnvMV4yHvmYqPaVRvJL5h"
    alert_threshold_pct: 0.5
  - label: "whale_3"
    address: "HLnpSzBvqJVxT2FmZBmqyHJ8dZB2oiQ31iM2k3Jxq3Yv"
    alert_threshold_pct: 0.5
  - label: "meteora_pool"
    address: "DbyK8gEiXwNeh2zFW2Lo1svuQ1WkHAeQyNDsRaKQ6BHf"
    is_pool: true
    alert_threshold_pct: 10.0

cex_wallets:
  - label: "binance"
    address: "5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9"
  - label: "coinbase"
    address: "H8sMJSCQxfKiFTCfDR3DUMLPwcRbM61LGFJ8N4dK3WjS"

settings:
  poll_interval_seconds: 30
  rpc_url: "https://your-helius-endpoint.com"
  log_file: "/var/log/ralph_tracker.log"
```

### Fast Polling (High Activity)

```yaml
token:
  address: "CxWPdDBqxVo3fnTMRTvNuSrd4gkp78udSrFvkVDBAGS"

wallets:
  - label: "whale_1"
    address: "FULL_ADDRESS"
    alert_threshold_pct: 0.1  # Very sensitive

settings:
  poll_interval_seconds: 10   # Fast polling
  rpc_url: "https://paid-rpc-endpoint.com"  # Need paid RPC for this
  max_retries: 5
```
