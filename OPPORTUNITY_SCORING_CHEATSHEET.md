# Opportunity Scoring - Quick Reference

## The Problem You Identified

**"Advanced analysis takes time to be reflected in price"**

- Twilio pops on earnings → but NDR 108% (below 110% threshold), growth 9% (below 25%)
- By the time we see "SELL" signal, may have missed exit opportunity
- Need to layer price action for timing

## The Solution: Opportunity Score (0-100)

```
Opportunity Score = Fundamental Strength + Valuation + Price Momentum + Technicals
                    (40 points)          (30 points)  (20 points)      (10 points)
```

### Scoring Breakdown

| Component | Strong Adds | Neutral | Weak Subtracts |
|-----------|-------------|---------|----------------|
| **Fundamentals** | STRONG_BUY: +20<br>BUY: +15 | WATCH: +5 | SELL: -15<br>AVOID: -20 |
| **Valuation** | Cheap P/S: +15<br>Fair P/S: +5 | - | Expensive: -10<br>Very Expensive: -20 |
| **Price** | >30% off highs: +15<br>>15% off highs: +10 | - | Near highs: -10 |
| **Technical** | RSI <30: +10 | RSI 30-70: 0 | RSI >70: -10 |

### Score Interpretation

| Score | Action | Meaning |
|-------|--------|---------|
| **80-100** | 🟢 BUY NOW | Mispricing - strong fundamentals, beaten down stock |
| **60-79** | 🟢 ACCUMULATE | Good opportunity - solid fundamentals, fair price |
| **40-59** | 🟡 MONITOR | Fair value - price matches fundamentals |
| **20-39** | 🟡 WAIT | Expensive - wait for pullback |
| **0-19** | 🔴 AVOID | Value trap - weak fundamentals, don't be fooled by low price |

## Four Key Patterns

### Pattern 1: MISPRICING (Score 80+)
```
✅ Fundamental: STRONG_BUY or BUY (NDR >110%, growth >20%)
✅ Valuation: CHEAP (P/S <10x for strong grower)
✅ Price: >20% off 52-week high
✅ Technical: RSI <40 (oversold)

→ Action: BUY NOW ⭐
→ Example: MongoDB -28% from highs, NDR 119%, P/S 8x
```

### Pattern 2: WAIT FOR PULLBACK (Score 20-40)
```
✅ Fundamental: STRONG_BUY or BUY
❌ Valuation: EXPENSIVE (P/S >20x)
❌ Price: Near 52-week high
❌ Technical: RSI >70 (overbought)

→ Action: WAIT FOR PULLBACK 🟡
→ Example: Snowflake near highs, P/S 22x despite elite 127% NDR
```

### Pattern 3: SELL RALLY (Score 20-30) ⭐ THIS CATCHES TWILIO
```
❌ Fundamental: SELL or WATCH (NDR <110%, growth <15%)
✅ Price: Recent rally >10% (earnings pop)
✅ Technical: Above moving averages

→ Action: SELL RALLY ⚠️
→ Example: Twilio +18% in 3mo but NDR 108%, growth 9%
```

### Pattern 4: VALUE TRAP (Score 0-20)
```
❌ Fundamental: SELL or AVOID (NDR <100%, growth <10%)
✅ Valuation: CHEAP (P/S <5x)
❌ Price: Down 40%+ from highs

→ Action: AVOID - VALUE TRAP 🔴
→ Example: Asana -45% from highs, NDR 96%, P/S 4x
```

## Valuation Tiers (P/S Ratio)

For companies with **strong fundamentals** (NDR >110%, growth >20%):

| P/S Ratio | Tier | Opportunity |
|-----------|------|-------------|
| <10x | **CHEAP** | ⭐ Buy (50% upside to fair value) |
| 10-15x | Fair | Reasonable entry |
| 15-25x | Expensive | Wait for pullback |
| >25x | Very Expensive | Avoid |

For companies with **weak fundamentals** (NDR <110%, growth <15%):

| P/S Ratio | Tier | Warning |
|-----------|------|---------|
| <8x | "Cheap" | Value trap - avoid |
| >12x | Expensive | Definitely avoid |

## Usage Workflow

### Weekly Scan
```bash
python plg_enhanced_analyzer.py
```

1. **Sort by opportunity score**
2. **Focus on 70+ scores** (mispricings)
3. **Review SELL RALLY signals** (exit opportunities)

### Quarterly (Post-Earnings)

1. **Update fundamental verdicts** - Did NDR change?
2. **Check for new mispricings**:
   - Did strong names sell off? (Buy opportunity)
   - Did weak names rally? (Exit opportunity)
3. **Rebalance portfolio**:
   - Exit score <30 names
   - Add to score 70+ names

## Real Example: Answering Your Question

**Twilio "Recently Popped After Good Earnings"**

Without opportunity scoring:
- Thesis says: SELL (NDR 108%, growth 9%)
- But you might think: "Maybe earnings beat means it's turning around?"

With opportunity scoring:
```
Fundamental verdict: SELL (NDR 108% below 110%, growth 9% below 25%)
+ Recent rally: +18% in 3 months
+ Valuation: P/S 2.8x (not expensive but not a reason to hold)
= Opportunity score: 22 (low)
= Timing signal: SELL RALLY ⚠️

Rationale: Short-term beat doesn't change deteriorating fundamentals.
The rally creates an exit opportunity before next quarter likely disappoints.
```

**Action**: Use the pop to exit. Fundamentals say this is a commoditizing business (APIs becoming table stakes, cloud providers bundling, growth decelerating). The earnings beat gave you a better exit price.

## The Key Insight

**Fundamental analysis (your thesis) = Quality filter** → Which companies to own?

**Opportunity scoring (price + valuation) = Timing filter** → When to buy/sell?

| Scenario | Thesis Says | Price Says | Combined Action |
|----------|-------------|------------|-----------------|
| MongoDB | BUY | Down 28%, RSI 35 | **BUY NOW** ⭐ (score 85) |
| Snowflake | STRONG_BUY | Near highs, RSI 68 | **WAIT** (score 42) |
| Twilio | SELL | Up 18%, rallying | **SELL RALLY** ⚠️ (score 22) |
| Asana | SELL | Down 45%, "cheap" | **AVOID TRAP** 🔴 (score 15) |

This bridges the gap between "advanced analysis" (slow/accurate) and "price action" (fast/noisy).
