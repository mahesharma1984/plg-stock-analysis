# Opportunity Scoring System - Catch Mispricings

## The Timing Problem

**Your observation is correct**: PLG thesis fundamentals are lagging indicators.

- **Twilio example**: Stock pops on "good" earnings even though NDR 108% (below 110% threshold) and growth 9% (well below 25%)
- **The gap**: Market reacts to quarterly beats/misses faster than fundamental deterioration shows up in NDR/growth trends
- **Risk**: By the time we see "SELL" signal, stock may have already fallen 30-50%

## Solution: Layer in Valuation + Price Action

The enhanced analyzer adds an **opportunity score (0-100)** that combines:

1. **Fundamental strength** (40 points) - Your thesis verdict
2. **Valuation** (30 points) - Is P/S ratio appropriate for growth rate?
3. **Price momentum** (20 points) - How far from 52-week high?
4. **Technical position** (10 points) - RSI, moving averages

### Opportunity Score Interpretation

| Score | Meaning | Action |
|-------|---------|--------|
| 80-100 | **Mispricing** - Strong fundamentals, beaten down stock | BUY NOW |
| 60-79 | **Good opportunity** - Solid fundamentals, fair/cheap valuation | ACCUMULATE |
| 40-59 | **Fair value** - Fundamentals match price | MONITOR |
| 20-39 | **Expensive** - Price ahead of fundamentals | WAIT FOR PULLBACK |
| 0-19 | **Value trap** - Weak fundamentals, avoid even if cheap | AVOID |

## Valuation Tiers

Based on your thesis benchmarks:

### For STRONG_BUY/BUY companies (NDR >110%, growth >20%):

| P/S Ratio | Tier | Justification |
|-----------|------|---------------|
| 15-25x | Fair/Expensive | Elite tier (NDR >120%, growth >30%) |
| 10-15x | Fair | Good tier (NDR 110-120%, growth 20-25%) |
| <10x | **CHEAP** | ⭐ Opportunity - market mispricing |
| >25x | Very Expensive | Wait for pullback |

### For WATCH/SELL companies (NDR <110% or growth <15%):

| P/S Ratio | Tier | Justification |
|-----------|------|---------------|
| >12x | Very Expensive | Sell rally if you own |
| 8-12x | Expensive | Fundamentals don't justify |
| <8x | Fair | But still avoid - value trap |

## Key Patterns to Catch

### Pattern 1: Mispricing (BUY NOW)
```
Fundamental Verdict: STRONG_BUY or BUY
+ Valuation: CHEAP (P/S <10x for strong grower)
+ Price: >20% off 52-week high
+ Technical: RSI <40 (oversold)
= Opportunity Score: 80-100 ⭐ BUY NOW
```

**Example from your thesis**: Monday.com dropped 27% on conservative guidance despite 27% growth, NDR 111%
- If P/S fell to 8-10x = buying opportunity
- Market overreacted to guidance vs. fundamental strength

### Pattern 2: Wait for Pullback
```
Fundamental Verdict: STRONG_BUY or BUY  
+ Valuation: EXPENSIVE (P/S >20x)
+ Price: Near 52-week high
+ Technical: RSI >70 (overbought)
= Opportunity Score: 30-50 → Wait
```

**This prevents**: Buying Snowflake at 40x P/S even with elite 127% NDR

### Pattern 3: Sell Rally (Exit Opportunity)
```
Fundamental Verdict: SELL or WATCH
+ Valuation: Still expensive
+ Price: Recent 3-month rally >10%
+ Technical: Above moving averages
= Timing Signal: SELL RALLY ⭐
```

**Example**: Twilio pops 15% on earnings beat
- But NDR 108% (below threshold), growth 9% (decelerating)
- Fundamental verdict: SELL
- Price action: Rallying
- **Action**: Exit into strength before next quarter disappoints

### Pattern 4: Value Trap (Avoid)
```
Fundamental Verdict: SELL or AVOID
+ Valuation: CHEAP (P/S <8x)
+ Price: Down 40%+ from highs
= Opportunity Score: 10-20 → VALUE TRAP
```

**Examples from your analysis**:
- Asana: NDR 96%, growth 10% (SELL verdict) - Even if P/S drops to 5x, avoid
- ZoomInfo: NDR 87%, revenue -1% (SELL verdict) - Cheap for a reason

## How to Use

### Weekly Review
1. **Run batch analyzer** - Get fundamental verdicts
2. **Run enhanced analyzer** - Add opportunity scores
3. **Sort by opportunity score** - Focus on 70+ scores
4. **Action tiers**:
   - Score 80+: Buy now (mispricings)
   - Score 60-79: Accumulate on dips
   - Score 40-59: Hold current positions
   - Score <40: Wait or exit

### Quarterly Review (Post-Earnings)
1. **Check for verdict changes** - Did NDR drop below 110%?
2. **Check for price action** - Did weak names rally? (Exit opportunity)
3. **Check for new opportunities** - Did strong names sell off? (Buy opportunity)

## Real-World Examples

### Scenario 1: Monday.com (Your Thesis)
- **Fundamental**: NDR 111%, growth 27% → WATCH (barely passing)
- **Price action**: Dropped 27% on guidance
- **If P/S falls to 8-10x**: Opportunity score jumps to 75+ → BUY NOW
- **Why**: Market overreacted, fundamentals still decent

### Scenario 2: Twilio (Your Question)
- **Fundamental**: NDR 108%, growth 9% → SELL
- **Price action**: Pops 15% on earnings beat
- **Current P/S**: Still 2-3x (not expensive but...)
- **Timing signal**: SELL RALLY
- **Why**: Short-term beat doesn't change deteriorating fundamentals

### Scenario 3: Datadog (Strong Name)
- **Fundamental**: NDR 120%, growth 28% → BUY
- **If price drops 25% on macro fears**: Opportunity score 85+ → STRONG BUY NOW
- **Why**: Fundamentals unchanged, market created entry point

## Implementation

### Quick Start
```bash
# Run enhanced analyzer on your portfolio
python plg_enhanced_analyzer.py

# Output includes:
# - Fundamental verdict (from thesis)
# - Valuation tier (cheap/fair/expensive)
# - Opportunity score (0-100)
# - Timing signal (buy_now/wait/sell_rally/avoid)
```

### Output Example
```
Ticker   Score  Recommendation           P/S    vs 52w High
------------------------------------------------------------
MDB      85     BUY NOW                  8.5x   -28%        ⭐ Opportunity
SNOW     72     BUY (Accumulate)        12.3x   -18%
TWLO     22     SELL (Exit on Rally)     2.8x   +12%        ⚠️ Exit
ASAN     15     AVOID (Value Trap)       4.2x   -45%        ⚠️ Trap
```

## Key Insights

1. **Timing matters**: Your thesis is fundamentally correct, but price action helps with entry/exit timing
2. **Mispricings exist**: Strong fundamentals + selloff = opportunity (Monday.com pattern)
3. **Avoid traps**: Cheap price ≠ good buy if fundamentals are weak (Asana, ZoomInfo)
4. **Exit discipline**: Weak fundamentals + rally = exit opportunity (Twilio pattern)
5. **Be contrarian**: When fundamentally strong names sell off on macro fears, that's when to buy

## Advanced: Why Valuation Matters

### The Math
```
Company A: NDR 120%, Growth 25%, P/S 15x → Fair value
Company B: NDR 120%, Growth 25%, P/S 8x  → CHEAP (50% upside to fair value!)

Same fundamentals, different prices = opportunity
```

### The Thesis Connection
Your thesis says: "Monday.com dropped 27% on conservative guidance despite 27% growth = mispricing opportunity"

**That's exactly what this system catches**:
- Fundamental verdict: WATCH (NDR 111% at threshold)
- Price action: Down 27%
- If valuation became cheap: Opportunity score jumps
- Signal: BUY NOW (market overreaction)

## Summary

You're right that fundamentals are "advanced analysis" that lags price action. The solution:

1. **Use thesis for fundamental quality** (NDR >110% = keeper)
2. **Use valuation for pricing** (P/S relative to growth)
3. **Use technicals for timing** (RSI, % off highs)
4. **Combine into opportunity score** (0-100)

**Best opportunities**: High fundamental quality + Low price = 80+ scores

This catches the Monday.com pattern (good fundamentals, market overreaction) while avoiding the Asana trap (cheap stock, broken fundamentals).
