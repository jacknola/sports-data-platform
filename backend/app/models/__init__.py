"""Database models"""

# Ensure models are imported so SQLAlchemy registers them during metadata creation
from .bet import Bet  # noqa: F401
from .game import Game  # noqa: F401
from .team import Team  # noqa: F401
from .player import Player  # noqa: F401
from .parlay import Parlay, ParlayLeg  # noqa: F401

