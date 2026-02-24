# Sports Betting Research Sources

## Core Repositories & Methodologies

### 1. [NBA-Machine-Learning-Sports-Betting](https://github.com/kyleskom/NBA-Machine-Learning-Sports-Betting)
- **Author**: Kyle Skom
- **Key Contribution**: XGBoost feature set for NBA moneyline and over/under.
- **Data Pipeline**: Automated stats fetching from Basketball-Reference and Odds APIs.

### 2. [nba_api](https://github.com/swar/nba_api)
- **Contribution**: Direct access to NBA.com stats. Used for live team pace, offensive rating, and defensive rating.

### 3. [Plus EV Model Research](https://github.com/chevyphillip/plus-ev-model)
- **Key Contribution**: Rolling averages and edge calculation logic.
- **Concept**: Finding discrepancies between sharp books and retail books using consensus true probability.

### 4. [NBA Prop Prediction](https://github.com/parlayparlor/nba-prop-prediction-model)
- **Key Contribution**: Projection logic for player props using hit-rate windows (Last 5, 10, 20).

---

## Academic & Quantitative Foundations

### 1. Kelly Criterion
- **Source**: "A New Interpretation of Information Rate" (J.L. Kelly, 1956).
- **Application**: Optimal bankroll management. Our system uses a **Fractional Kelly (Quarter/Half)** to account for model variance.

### 2. Bayesian Inference in Sports
- **Concept**: Updating a prior (market odds) with new evidence (ML predictions).
- **Benefit**: Reduces overconfidence in pure ML models and respects market efficiency.

### 3. Market Efficiency & CLV
- **Research**: Closing Line Value (CLV) as the primary metric for long-term profitability.
- **Strategy**: Consistently beating the closing line at sharp books (Pinnacle) leads to sustainable edge.

---

## Market Signal Research

### 1. Reverse Line Movement (RLM)
- Identifying when professional money moves the line in the opposite direction of public betting volume (tickets).

### 2. Steam Moves
- Sudden, coordinated movements across multiple market-maker sportsbooks indicating a syndicate wager.

### 3. Line Freeze
- Situations where 80%+ of public action is on one side, yet the line remains static, indicating bookmaker confidence in the sharp side.
