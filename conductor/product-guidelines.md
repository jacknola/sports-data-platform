# Product Guidelines

## Prose Style & Tone
- **Technical & Precision-Oriented:** Use precise terminology (EV, CLV, devigging, RLM). Avoid vague marketing language.
- **High Signal-to-Noise:** Communication (logs, reports, UI) should prioritize actionable data over flavor text.
- **Direct & Analytical:** Maintain a professional, quantitative tone. Insights should be backed by numbers or logic.
- **Concise:** Favor brevity in reporting (Telegram/Twitter) while providing depth in detailed analysis (Notion/Sheets).

## Branding & Visual Identity
- **Quant-Focused:** The "brand" is a professional sports betting syndicate/quant desk.
- **Color Palette:** Professional, high-contrast colors (e.g., Emerald for profit, Crimson for loss, Deep Slate for background).
- **Typography:** Clean, monospaced fonts for data tables and technical logs to emphasize mathematical rigor.

## User Experience (UX) Principles
- **Data-First:** The UI and reports must lead with the most important data points (Edge %, Kelly Size, Confidence).
- **Automation by Default:** Minimize manual intervention. The system should alert the user only when action is required or a significant signal is detected.
- **Traceability:** Every recommendation must be traceable back to its source data (e.g., "Odds from Pinnacle at 14:02 UTC").
- **Interactive Feedback:** Real-time updates for live signals (Steam, RLM) to ensure timely wagering.

## Documentation Standards
- **Mathematical Transparency:** All models and formulas must be documented clearly in the code or internal guides.
- **Agent Roles:** Each agent's responsibilities and decision logic must be explicitly defined.
- **Error Transparency:** Failures (scraping errors, API timeouts) should be logged with enough context for quick diagnosis.
