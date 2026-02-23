"""
Centralized constants for the Sports Data Intelligence Platform.

All hardcoded values that were previously scattered across services
are now consolidated here for consistency and maintainability.
"""

from typing import Dict, FrozenSet, Set

# ============================================================================
# KELLY CRITERION CONSTANTS
# ============================================================================

# Default Kelly scaling (fraction of full Kelly to use)
# 0.5 = Half-Kelly (most common, recommended for most bettors)
# 0.25 = Quarter-Kelly (conservative)
# 1.0 = Full Kelly (aggressive, high variance)
KELLY_SCALE_DEFAULT: float = 0.5

# Maximum fraction of bankroll for any single bet
KELLY_MAX_SINGLE_FRACTION: float = 0.05  # 5%

# Maximum total bankroll exposure across all simultaneous bets
KELLY_MAX_TOTAL_EXPOSURE: float = 0.25  # 25%

# Sharp signal boost multiplier for Kelly calculations
KELLY_SHARP_SIGNAL_BOOST_MULTIPLIER: float = 0.02


# ============================================================================
# EDGE & EV THRESHOLDS
# ============================================================================

# Minimum edge (in probability units) to consider a bet
# Standard: 0.03 (3% edge required)
MIN_EDGE_DEFAULT: float = 0.03

# Sport-specific edge thresholds (can be more/less aggressive)
MIN_EDGE_NCAAB: float = 0.025  # 2.5% - NCAAB markets less efficient
MIN_EDGE_NBA: float = 0.025  # 2.5% - same for NBA
MIN_EDGE_NFL: float = 0.03  # 3.0% - NFL markets more efficient
MIN_EDGE_PROPS: float = 0.03  # 3.0% for player props
MIN_EDGE_LIVE: float = 0.05  # 5.0% for live betting (higher variance)

# Strong play threshold (for display/reporting)
EDGE_STRONG_PLAY: float = 0.05  # 5%+ = strong play emoji

# Minimum Kelly fraction to display a bet
MIN_KELLY_DISPLAY: float = 0.001  # 0.1%


# ============================================================================
# SPORT IDENTIFIERS
# ============================================================================

# Internal sport keys (used throughout the app)
SPORT_NFL: str = "nfl"
SPORT_NBA: str = "nba"
SPORT_NCAAB: str = "ncaab"
SPORT_NCAAF: str = "ncaaf"
SPORT_MLB: str = "mlb"
SPORT_NHL: str = "nhl"
SPORT_SOCCER: str = "soccer"

# Odds API sport keys (used for API calls)
ODDS_API_SPORT_NBA: str = "basketball_nba"
ODDS_API_SPORT_NCAAB: str = "basketball_ncaab"
ODDS_API_SPORT_NFL: str = "americanfootball_nfl"
ODDS_API_SPORT_NCAAF: str = "americanfootball_ncaaf"
ODDS_API_SPORT_MLB: str = "baseball_mlb"
ODDS_API_SPORT_NHL: str = "icehockey_nhl"

# Mapping from internal sport to Odds API sport
SPORT_TO_ODDS_API: Dict[str, str] = {
    SPORT_NBA: ODDS_API_SPORT_NBA,
    SPORT_NCAAB: ODDS_API_SPORT_NCAAB,
    SPORT_NFL: ODDS_API_SPORT_NFL,
    SPORT_NCAAF: ODDS_API_SPORT_NCAAF,
    SPORT_MLB: ODDS_API_SPORT_MLB,
    SPORT_NHL: ODDS_API_SPORT_NHL,
}


# ============================================================================
# MARKET TYPES
# ============================================================================

MARKET_SPREAD: str = "spread"
MARKET_TOTAL: str = "total"
MARKET_MONEYLINE: str = "moneyline"
MARKET_H2H: str = "h2h"

# Markets to request from Odds API
ODDS_API_MARKETS: str = "h2h,spreads,totals"


# ============================================================================
# BOOKMAKER IDENTIFIERS
# ============================================================================

# Sharp books (used for devigging and line movement detection)
BOOKMAKER_PINNACLE: str = "pinnacle"
BOOKMAKER_CIRCA: str = "circa"

# Retail books (where we find +EV)
BOOKMAKER_DRAFTKINGS: str = "draftkings"
BOOKMAKER_FANDUEL: str = "fanduel"
BOOKMAKER_BETMGM: str = "betmgmt"
BOOKMAKER_CAESARS: str = "caesars"
BOOKMAKER_BOVADA: str = "bovada"
BOOKMAKER_BET365: str = "bet365"

# Set of sharp books for reference
SHARP_BOOKMAKERS: FrozenSet[str] = frozenset({BOOKMAKER_PINNACLE, BOOKMAKER_CIRCA})

# Set of retail books for reference
RETAIL_BOOKMAKERS: FrozenSet[str] = frozenset(
    {
        BOOKMAKER_DRAFTKINGS,
        BOOKMAKER_FANDUEL,
        BOOKMAKER_BETMGM,
        BOOKMAKER_CAESARS,
        BOOKMAKER_BOVADA,
        BOOKMAKER_BET365,
    }
)

# All bookmakers to check (priority order for odds lookup)
BOOKMAKER_PRIORITY: list = [
    BOOKMAKER_PINNACLE,
    BOOKMAKER_CIRCA,
    BOOKMAKER_DRAFTKINGS,
    BOOKMAKER_FANDUEL,
    BOOKMAKER_BETMGM,
    BOOKMAKER_CAESARS,
    BOOKMAKER_BOVADA,
    BOOKMAKER_BET365,
]


# ============================================================================
# RLM (REVERSE LINE MOVEMENT) DETECTION
# ============================================================================

# Minimum public ticket % on one side to be considered "one-sided"
RLM_TICKET_THRESHOLD: float = 0.65  # 65%

# Minimum gap between ticket % and money % to validate sharp signal
RLM_GAP_THRESHOLD: float = 0.10  # 10%

# Gap size for high confidence RLM signal
RLM_HIGH_CONFIDENCE_GAP: float = 0.20  # 20%


# ============================================================================
# STEAM MOVE DETECTION
# ============================================================================

# Line movement thresholds (must move this much within STEAM_WINDOW_SECONDS)
STEAM_LINE_MOVE_SPREAD: float = 0.5  # half-point on spreads
STEAM_LINE_MOVE_TOTAL: float = 1.0  # full point on totals
STEAM_ODDS_MOVE: int = 8  # 8 cents on moneylines

# Time window for steam detection (seconds)
STEAM_WINDOW_SECONDS: int = 60

# Minimum number of books that must move for steam confirmation
STEAM_MIN_BOOKS: int = 3

# Prop-specific: juice shift threshold (cents)
JUICE_SHIFT_THRESHOLD: int = 10  # 10-cent vig swing without line move
# Prop-specific: steam line move threshold
STEAM_LINE_MOVE_PROP: float = 0.5  # half-point on prop total


# ============================================================================
# LINE FREEZE DETECTION
# ============================================================================

# Public ticket % threshold to trigger freeze check
FREEZE_TICKET_THRESHOLD: float = 0.80  # 80%

# Maximum line movement allowed while still considered "frozen"
FREEZE_MAX_LINE_MOVE: float = 0.25


# ============================================================================
# HEAD FAKE DETECTION
# ============================================================================

# Minutes within which a line reversal is considered a potential head fake
HEAD_FAKE_REVERSAL_MINUTES: int = 15

# Volatility multiplier for head fake detection (>= this * historical vol)
HEAD_FAKE_VOLATILITY_MULTIPLIER: float = 2.0


# ============================================================================
# CONFIDENCE THRESHOLDS
# ============================================================================

CONFIDENCE_VERY_HIGH: float = 0.80
CONFIDENCE_HIGH: float = 0.65
CONFIDENCE_MEDIUM: float = 0.50
CONFIDENCE_LOW: float = 0.35


# ============================================================================
# SPREAD & LINE THRESHOLDS
# ============================================================================

# Spread sizes that trigger variance risk flags
LARGE_SPREAD_THRESHOLD: float = 7.5  # Points
MEDIUM_SPREAD_THRESHOLD: float = 5.0  # Points

# Line unchanged threshold for freeze detection
LINE_UNCHANGED_THRESHOLD: float = 0.25


# ============================================================================
# CONFERENCE TIERS (for variance penalties)
# ============================================================================

CONFERENCE_TIER_POWER_5: str = "power_5"
CONFERENCE_TIER_HIGH_MAJOR: str = "high_major"
CONFERENCE_TIER_MID_MAJOR: str = "mid_major"
CONFERENCE_TIER_LOW_MAJOR: str = "low_major"

# Probability penalties by conference tier and spread bucket
CONFERENCE_TIER_SPREAD_PENALTY: Dict[str, Dict[str, float]] = {
    CONFERENCE_TIER_POWER_5: {"large": 0.00, "medium": 0.00},
    CONFERENCE_TIER_HIGH_MAJOR: {"large": -0.02, "medium": -0.01},
    CONFERENCE_TIER_MID_MAJOR: {"large": -0.05, "medium": -0.02},
    CONFERENCE_TIER_LOW_MAJOR: {"large": -0.08, "medium": -0.04},
}

# Non-power-5 conferences for spread variance calculations
NON_POWER_5_CONFERENCES: Set[str] = {
    "mac",
    "sun_belt",
    "cusa",
    "ovc",
    "colonial",
    "big_south",
    "horizon",
    "swac",
    "meac",
    "patriot",
    "nec",
    "big_sky",
    "southern",
    "america_east",
    "american",
    "mountain_west",
    "wcc",
    "a10",
    "mvc",
}


# ============================================================================
# CORRELATION ESTIMATES (for portfolio optimization)
# ============================================================================

# Correlation between different bet types
CORR_SAME_GAME_SPREAD_TOTAL: float = 0.60
CORR_SAME_GAME_SAME_MARKET: float = 0.85
CORR_BACK_TO_BACK_SAME_TEAM: float = 0.30
CORR_SAME_CONFERENCE_SAME_DAY: float = 0.18
CORR_SAME_DIVISION_SAME_DAY: float = 0.22
CORR_CROSS_CONFERENCE_SAME_DAY: float = 0.08
CORR_DIFFERENT_SPORT: float = 0.02


# ============================================================================
# BAYESIAN ADJUSTMENTS
# ============================================================================

# Injury status adjustments
INJURY_QUESTIONABLE_PENALTY: float = -0.05
INJURY_OUT_PENALTY: float = -0.99

# Home court advantage
HOME_ADVANTAGE: float = 0.03
AWAY_PENALTY: float = -0.03

# Weather adjustments (outdoor sports)
WEATHER_HIGH_WIND_THRESHOLD: float = 20.0  # mph
WEATHER_HIGH_WIND_PENALTY: float = -0.03

# Pace adjustment multiplier
PACE_ADJUSTMENT_MULTIPLIER: float = 0.1

# Usage trend multiplier
USAGE_TREND_MULTIPLIER: float = 0.02

# Form adjustment multiplier
FORM_ADJUSTMENT_MULTIPLIER: float = 0.1


# ============================================================================
# GAME DURATION (minutes)
# ============================================================================

NBA_GAME_MINUTES: float = 48.0
NCAAB_GAME_MINUTES: float = 40.0
NFL_GAME_MINUTES: float = 60.0

# Foul limits
NBA_FOUL_LIMIT: int = 6
NCAAB_FOUL_LIMIT: int = 5

# Foul limits as dict keyed by sport (for live prop engine)
FOUL_LIMITS: Dict[str, int] = {
    SPORT_NBA: NBA_FOUL_LIMIT,
    SPORT_NCAAB: NCAAB_FOUL_LIMIT,
}


# ============================================================================
# API CONFIGURATION
# ============================================================================

# API timeouts (seconds)
DEFAULT_API_TIMEOUT: float = 30.0
TELEGRAM_API_TIMEOUT: float = 15.0
WEB_SCRAPER_TIMEOUT: float = 30.0

# Telegram polling
TELEGRAM_POLLING_TIMEOUT: int = 10
TELEGRAM_LONG_POLLING_TIMEOUT: int = 5

# Rate limiting
TELEGRAM_RATE_LIMIT_DELAY: float = 1.0
TELEGRAM_MAX_RETRIES: int = 3

# Message limits
TELEGRAM_MAX_MESSAGE_LENGTH: int = 4096


# ============================================================================
# API URLs
# ============================================================================

ODDS_API_BASE_URL: str = "https://api.the-odds-api.com/v4"
TELEGRAM_API_BASE_URL: str = "https://api.telegram.org"


# ============================================================================
# PROBABILITY CALCULATION DEFAULTS
# ============================================================================

# League averages
LEAGUE_AVG_PACE: float = 100.0
LEAGUE_AVG_DEF_RATING: float = 113.5
LEAGUE_AVG_OFF_RATING: float = 113.5

# Minimum standard deviation for prop calculations
MIN_STD_DEFAULT: float = 1.0
MIN_STD_LIVE: float = 0.5

# Stat standard deviation factors (percentage of mean)
STAT_STD_FACTOR_LOW: float = 0.40
STAT_STD_FACTOR_MEDIUM: float = 0.50
STAT_STD_FACTOR_HIGH: float = 0.60

# Stat standard deviation factors by stat type (for prop models)
STAT_STD_FACTORS: Dict[str, float] = {
    'points':   0.40,
    'rebounds': 0.45,
    'assists':  0.50,
    'threes':   0.55,
    'blocks':   0.60,
    'steals':   0.60,
    'pra':      0.35,  # points + rebounds + assists (diversified, lower CV)
}


# ============================================================================
# MONTE CARLO SIMULATION
# ============================================================================

MONTE_CARLO_SIMULATIONS: int = 20000
BAYESIAN_PRIOR_STRENGTH: int = 10
BAYESIAN_PSEUDO_OBSERVATIONS: int = 20


# ============================================================================
# RISK SCORE THRESHOLDS
# ============================================================================

RISK_SCORE_HIGH: float = 0.50
RISK_SCORE_MODERATE: float = 0.25

# Parlay risk factors
PARLAY_RISK_SCORE_LEG_MULTIPLIER: float = 0.18
PARLAY_RISK_SCORE_LARGE_SIZE: float = 0.40
PARLAY_RISK_SCORE_MEDIUM_SIZE: float = 0.20
PARLAY_RISK_SCORE_SPORT_CONCENTRATION: float = 0.10

# Parlay size thresholds
PARLAY_SIZE_LARGE: int = 9
PARLAY_SIZE_MEDIUM: int = 7
PARLAY_SIZE_SMALL: int = 5


# ============================================================================
# DEFAULT DISPLAY FORMATTING
# ============================================================================

PROBABILITY_DECIMAL_PLACES: int = 4
EDGE_DECIMAL_PLACES: int = 2
ODDS_DECIMAL_PLACES: int = 3
KELLY_FRACTION_DECIMAL_PLACES: int = 4

# Human-like fraction rounding (nearest 0.25% of bankroll)
FRACTION_ROUNDING_DENOMINATOR: int = 400  # rounds to nearest 0.25%


# ============================================================================
# TIME TO LIVE (TTL) VALUES
# ============================================================================

# Cache TTL (seconds)
REDIS_CACHE_TTL_DAYS: int = 90
AGENT_MEMORY_TTL_DAYS: int = 30

REDIS_CACHE_TTL: int = REDIS_CACHE_TTL_DAYS * 86400
AGENT_MEMORY_TTL: int = AGENT_MEMORY_TTL_DAYS * 86400
