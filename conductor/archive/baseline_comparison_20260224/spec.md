# Track Specification: Implement Baseline Model Comparison

## Objective
The primary goal of this track is to establish a rigorous evaluation framework to compare the predictive performance of the existing Bayesian models against a classical Machine Learning approach (Random Forest). This will help determine the most effective architecture for identifying +EV wagering opportunities.

## Scope

### 1. Data Preparation
- Extraction of historical game outcomes and pre-game odds (sharp and retail).
- Feature engineering for both Bayesian (probabilistic priors) and Random Forest (tabular features).
- Split data into training and validation sets.

### 2. Random Forest Implementation
- Implement a Random Forest Regressor/Classifier to predict win probabilities or point spreads.
- Optimize hyperparameters using cross-validation.

### 3. Evaluation Framework
- Implement core betting metrics:
    - **Brier Score:** To measure probability calibration.
    - **ROI:** Simulated return on investment using Kelly Criterion.
    - **CLV (Closing Line Value):** Ability to beat the closing sharp lines.
- Create a visualization/reporting tool to compare model performance side-by-side.

### 4. Analysis & Reporting
- Run the comparison on a specific historical period (e.g., the last 30 days of NBA/NCAAB data).
- Generate a summary report with recommendations on which model(s) to move forward with.

## Success Criteria
- [ ] Random Forest model is successfully trained and optimized.
- [ ] Evaluation framework provides consistent metrics for both models.
- [ ] Comparative report clearly identifies the superior model across different metrics (Accuracy, ROI, CLV).
- [ ] Automated reporting of comparison results to the project logs/Notion.

## Technical Constraints
- Must adhere to the existing multi-agent architecture (could be implemented as a new `AnalysisAgent` variant).
- Must use `loguru` for all analysis logging.
- Tests must achieve >80% coverage for the new evaluation modules.
