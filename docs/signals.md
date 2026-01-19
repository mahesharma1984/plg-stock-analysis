# Signals Reference

Complete guide to signals detected by the RALPH Whale Tracker.

## Signal Overview

The tracker monitors wallet balances and detects patterns that may indicate trading opportunities or risks.

| Signal | Trigger | Severity | Sentiment |
|--------|---------|----------|-----------|
| `WHALE_BUY` | Balance increase | INFO | Bullish |
| `WHALE_SELL` | Balance decrease | WARNING | Bearish |
| `WHALE_TO_CEX` | Transfer to exchange | CRITICAL | Very Bearish |
| `LIQUIDITY_DROP` | Pool depth -10%+ | WARNING | Bearish |
| `LIQUIDITY_ADD` | Pool depth +10%+ | INFO | Bullish |
| `ACCUMULATION` | 2+ whales buying | INFO | Very Bullish |
| `DISTRIBUTION` | 2+ whales selling | WARNING | Very Bearish |

---

## Signal Details

### WHALE_BUY

**Trigger:** A tracked wallet's RALPH balance increases above the configured threshold.

**Severity:** INFO (Green)

**What it means:**
- A whale is accumulating more tokens
- Could indicate confidence in the project
- May precede price appreciation

**Example output:**
```
[2026-01-19 14:45:22] WHALE_BUY | whale_1 bought 2.1M RALPH (+2.25%)
         New balance: 95.4M (9.54% of supply)
         Tx: 4xK9f... view on Solscan
```

**Log format:**
```
2026-01-19T14:45:22Z|INFO|WHALE_BUY|whale_1|95400000|9.54|+2100000|4xK9f...
```

**Trading consideration:** Generally bullish. Consider the size of the buy relative to typical volume.

---

### WHALE_SELL

**Trigger:** A tracked wallet's RALPH balance decreases above the configured threshold.

**Severity:** WARNING (Red)

**What it means:**
- A whale is reducing their position
- Could indicate loss of confidence
- May precede price decline

**Example output:**
```
[2026-01-19 16:12:08] WHALE_SELL | whale_2 sold 5M RALPH (-10.9%)
         New balance: 40.8M (4.08% of supply)
         Tx: 7yH2a... view on Solscan
```

**Log format:**
```
2026-01-19T16:12:08Z|WARNING|WHALE_SELL|whale_2|40800000|4.08|-5000000|7yH2a...
```

**Trading consideration:** Bearish signal. Larger sells and multiple whales selling are more significant.

---

### WHALE_TO_CEX

**Trigger:** A tracked wallet transfers RALPH to a known centralized exchange (CEX) wallet.

**Severity:** CRITICAL (Red, Bold)

**What it means:**
- Whale is moving tokens to an exchange
- Strong indication of intent to sell
- Often precedes significant price dumps

**Example output:**
```
[2026-01-19 18:30:45] CRITICAL: WHALE_TO_CEX | whale_3 transferred 10M RALPH to binance
         Potential dump incoming - consider exit
```

**Log format:**
```
2026-01-19T18:30:45Z|CRITICAL|WHALE_TO_CEX|whale_3|binance|10000000|8jP3q...
```

**Trading consideration:** High-priority bearish signal. Consider reducing position or setting stop losses.

**Known CEX addresses tracked:**
| Exchange | Address |
|----------|---------|
| Binance | `5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9` |
| Coinbase | `H8sMJSCQxfKiFTCfDR3DUMLPwcRbM61LGFJ8N4dK3WjS` |

---

### LIQUIDITY_DROP

**Trigger:** Liquidity pool token balance decreases by more than threshold (default 10%).

**Severity:** WARNING (Red)

**What it means:**
- Liquidity is being removed from the pool
- Reduces available exit liquidity
- Higher slippage for trades
- Could indicate LP losing confidence

**Example output:**
```
[2026-01-19 20:15:33] LIQUIDITY_DROP | Pool depth decreased by 15.2%
         New balance: 127.4M (12.74% of supply)
```

**Log format:**
```
2026-01-19T20:15:33Z|WARNING|LIQUIDITY_DROP|liquidity_pool|127400000|12.74|-22600000|...
```

**Trading consideration:** Bearish. Reduced liquidity makes it harder to exit positions without significant slippage.

---

### LIQUIDITY_ADD

**Trigger:** Liquidity pool token balance increases by more than threshold (default 10%).

**Severity:** INFO (Green)

**What it means:**
- Liquidity is being added to the pool
- Improves trading conditions
- Lower slippage for trades
- Shows LP confidence

**Example output:**
```
[2026-01-19 10:22:11] LIQUIDITY_ADD | Pool depth increased by 12.5%
         New balance: 168.8M (16.88% of supply)
```

**Log format:**
```
2026-01-19T10:22:11Z|INFO|LIQUIDITY_ADD|liquidity_pool|168800000|16.88|+18800000|...
```

**Trading consideration:** Bullish. Better liquidity conditions for entering/exiting positions.

---

### ACCUMULATION

**Trigger:** Two or more different whales buy on the same day.

**Severity:** INFO (Green)

**What it means:**
- Multiple large holders are buying
- Coordinated or coincidental bullish behavior
- Strong demand from sophisticated traders
- Often precedes significant price moves

**Example output:**
```
[2026-01-19 16:00:00] ACCUMULATION | Multiple whales buying: whale_1, whale_2, whale_3
```

**Log format:**
```
2026-01-19T16:00:00Z|INFO|ACCUMULATION|whale_1, whale_2, whale_3|0|0.00|0|
```

**Trading consideration:** Very bullish. Multiple whales buying simultaneously is a strong positive signal.

---

### DISTRIBUTION

**Trigger:** Two or more different whales sell on the same day.

**Severity:** WARNING (Red)

**What it means:**
- Multiple large holders are selling
- Coordinated or coincidental bearish behavior
- Strong selling pressure from sophisticated traders
- Often precedes significant price drops

**Example output:**
```
[2026-01-19 18:00:00] DISTRIBUTION | Multiple whales selling: whale_2, whale_3
```

**Log format:**
```
2026-01-19T18:00:00Z|WARNING|DISTRIBUTION|whale_2, whale_3|0|0.00|0|
```

**Trading consideration:** Very bearish. Multiple whales selling simultaneously is a strong negative signal.

---

## Signal Priority Matrix

When multiple signals occur, prioritize by severity:

| Priority | Signals | Action |
|----------|---------|--------|
| 1 (Highest) | `WHALE_TO_CEX` | Immediate attention - consider exit |
| 2 | `DISTRIBUTION` | High alert - prepare to reduce |
| 3 | `WHALE_SELL`, `LIQUIDITY_DROP` | Monitor closely |
| 4 | `WHALE_BUY`, `LIQUIDITY_ADD` | Positive indicators |
| 5 (Lowest) | `ACCUMULATION` | Strong positive signal |

---

## Reading the Log File

The log file (`ralph_tracker.log`) uses a pipe-delimited format:

```
TIMESTAMP|SEVERITY|SIGNAL_TYPE|WALLET_LABEL|BALANCE|PCT_SUPPLY|AMOUNT_CHANGE|TX_SIGNATURE
```

**Examples:**

```
# Normal poll (no change)
2026-01-19T14:33:15Z|INFO|POLL|whale_1|93300000|9.33|NO_CHANGE

# Buy signal
2026-01-19T14:45:22Z|INFO|WHALE_BUY|whale_1|95400000|9.54|+2100000|4xK9f...

# Sell signal
2026-01-19T16:12:08Z|WARNING|WHALE_SELL|whale_2|40800000|4.08|-5000000|7yH2a...

# CEX transfer
2026-01-19T18:30:45Z|CRITICAL|WHALE_TO_CEX|whale_3|binance|10000000|8jP3q...
```

### Parsing the Log

**Bash example:**
```bash
# Get all sells from today
grep "WHALE_SELL" ralph_tracker.log | grep "2026-01-19"

# Count signals by type
cut -d'|' -f3 ralph_tracker.log | sort | uniq -c

# Get all critical alerts
grep "CRITICAL" ralph_tracker.log
```

**Python example:**
```python
with open('ralph_tracker.log') as f:
    for line in f:
        parts = line.strip().split('|')
        if len(parts) >= 3:
            timestamp, severity, signal_type = parts[:3]
            if signal_type == 'WHALE_SELL':
                print(f"Sell detected: {line}")
```

---

## Customizing Thresholds

Adjust sensitivity via `alert_threshold_pct` in config:

```yaml
wallets:
  - label: "whale_1"
    address: "..."
    alert_threshold_pct: 0.5   # Alert on 0.5% change (more sensitive)

  - label: "liquidity_pool"
    address: "..."
    is_pool: true
    alert_threshold_pct: 10.0  # Alert on 10% change (less sensitive)
```

| Threshold | Sensitivity | Use Case |
|-----------|-------------|----------|
| 0.1% | Very High | Tracking every small move |
| 0.5% | High | Active trading |
| 1.0% | Medium | Default, significant moves |
| 2.0% | Low | Only large moves |
| 5.0% | Very Low | Major events only |

---

## False Positives

Some signals may not indicate trading intent:

| Signal | Possible False Positive |
|--------|------------------------|
| `WHALE_BUY` | Token airdrop, OTC deal |
| `WHALE_SELL` | Transfer to cold wallet, OTC deal |
| `WHALE_TO_CEX` | Moving for staking, collateral |
| `LIQUIDITY_DROP` | Rebalancing LP position |

**Best Practice:** Always verify significant signals on [Solscan](https://solscan.io) before making trading decisions.
