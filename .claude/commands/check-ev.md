Calculate Expected Value and devigged probabilities for a bet given American odds.

Ask the user for the following if not already provided in their message:
- Pinnacle/sharp book odds for Side A (American format, e.g. -108)
- Pinnacle/sharp book odds for Side B (American format, e.g. -108)
- Retail book odds for the side you want to bet (American format, e.g. -110)
- (Optional) KenPom or model probability for the side (decimal, e.g. 0.54)

Then compute and display:

**Devig calculation:**
```
implied_A = |odds_A| / (|odds_A| + 100)   [if negative]
implied_A = 100 / (odds_A + 100)           [if positive]
total_vig = implied_A + implied_B
true_prob_A = implied_A / total_vig
true_prob_B = implied_B / total_vig
```

**Model blend (if KenPom/model prob provided):**
```
blended_prob = 0.60 * true_prob + 0.40 * model_prob
```

**Edge vs retail:**
```
retail_implied = compute from retail odds
edge = blended_prob - retail_implied
edge_pct = edge * 100
```

**Kelly fraction (Half-Kelly):**
```
b = decimal_retail_odds - 1
kelly_full = (p * b - (1-p)) / b
kelly_half = kelly_full * 0.50
kelly_quarter = kelly_full * 0.25
```

**EV per $100:**
```
ev = (p * (decimal_odds - 1) - (1-p)) * 100
```

Display a clean table with: True Prob | Blended Prob | Edge | Half-Kelly % | EV per $100 | Verdict (PLAY / PASS / STRONG PLAY)

Thresholds:
- PASS: edge < 2.5%
- PLAY: edge 2.5%–5.0%
- STRONG PLAY: edge > 5.0% + sharp signal confirmed
