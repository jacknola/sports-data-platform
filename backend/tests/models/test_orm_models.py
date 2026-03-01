"""
ORM model tests using SQLite in-memory database.

Tests verify that models can be persisted and retrieved correctly,
default values are applied, and nullable/non-nullable constraints work.
"""
import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.bet import Bet
from app.models.game import Game


# ---------------------------------------------------------------------------
# Module-scoped SQLite engine (all tables created once per test run)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine():
    # Import all models so they register with Base.metadata
    from app.models import bet, game, team, player  # noqa: F401
    e = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(e)
    yield e
    Base.metadata.drop_all(e)


@pytest.fixture
def session(engine):
    """Function-scoped session using a connection-level outer transaction.

    Even if the test calls session.commit(), the outer transaction wraps all
    changes and is rolled back on teardown — keeping tests perfectly isolated.
    """
    connection = engine.connect()
    outer_txn = connection.begin()
    Session = sessionmaker(bind=connection)
    s = Session()
    yield s
    s.close()
    outer_txn.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# Helper: create a persisted Game row
# ---------------------------------------------------------------------------

def _make_game(session, suffix="001", spread=None):
    game = Game(
        external_game_id=f"NBA_20260222_{suffix}",
        sport="NBA",
        home_team="Los Angeles Lakers",
        away_team="Boston Celtics",
        game_date=datetime.datetime(2026, 2, 22, 20, 0),
    )
    session.add(game)
    return game


# ---------------------------------------------------------------------------
# Game model
# ---------------------------------------------------------------------------

class TestGameModel:
    def test_create_and_retrieve(self, session):
        game = _make_game(session, "G01")
        fetched = session.query(Game).filter_by(external_game_id="NBA_20260222_G01").first()
        assert fetched is not None
        assert fetched.home_team == "Los Angeles Lakers"
        assert fetched.away_team == "Boston Celtics"

    def test_sport_stored(self, session):
        game = _make_game(session, "G02")
        fetched = session.query(Game).filter_by(external_game_id="NBA_20260222_G02").first()
        assert fetched.sport == "NBA"

    def test_game_date_stored(self, session):
        game = _make_game(session, "G03")
        fetched = session.query(Game).filter_by(external_game_id="NBA_20260222_G03").first()
        assert fetched.game_date == datetime.datetime(2026, 2, 22, 20, 0)

    def test_created_at_auto_populated(self, session):
        game = _make_game(session, "G04")
        session.flush()
        assert game.created_at is not None
        assert isinstance(game.created_at, datetime.datetime)

    def test_scores_are_nullable(self, session):
        game = _make_game(session, "G05")
        fetched = session.query(Game).filter_by(external_game_id="NBA_20260222_G05").first()
        assert fetched.home_score is None
        assert fetched.away_score is None

    def test_scores_can_be_set(self, session):
        game = _make_game(session, "G06")
        game.home_score = 112
        game.away_score = 108
        fetched = session.query(Game).filter_by(external_game_id="NBA_20260222_G06").first()
        assert fetched.home_score == 112
        assert fetched.away_score == 108

    def test_primary_key_auto_assigned(self, session):
        game = _make_game(session, "G07")
        session.flush()
        assert game.id is not None
        assert isinstance(game.id, int)

    def test_external_game_id_unique(self, session):
        from sqlalchemy.exc import IntegrityError
        _make_game(session, "G08")

        game2 = Game(
            external_game_id="NBA_20260222_G08",
            sport="NBA",
            home_team="GSW",
            away_team="MIA",
            game_date=datetime.datetime(2026, 2, 22, 22, 0),
        )
        session.add(game2)
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()
        session.rollback()


# ---------------------------------------------------------------------------
# Bet model
# ---------------------------------------------------------------------------

class TestBetModel:
    @pytest.fixture
    def game(self, session):
        g = _make_game(session, suffix="BET_BASE")
        session.flush()
        return g

    def test_create_and_retrieve(self, session, game):
        bet = Bet(
            selection_id="SEL_001",
            sport="NBA",
            game_id=game.id,
            team="Los Angeles Lakers",
            market="moneyline",
            current_odds=-150.0,
            implied_prob=0.60,
            devig_prob=0.62,
            posterior_prob=0.64,
            fair_american_odds=-177.8,
            edge=0.04,
            kelly_fraction=0.08,
        )
        session.add(bet)
        fetched = session.query(Bet).filter_by(selection_id="SEL_001").first()
        assert fetched is not None
        assert fetched.market == "moneyline"
        assert fetched.edge == pytest.approx(0.04)
        assert fetched.kelly_fraction == pytest.approx(0.08)

    def test_json_features_round_trip(self, session, game):
        features = {
            "injury_status": "ACTIVE",
            "is_home": True,
            "team_pace": 105.3,
            "recent_form": [1, 0, 1, 1, 0],
        }
        bet = Bet(
            selection_id="SEL_002",
            sport="NBA",
            game_id=game.id,
            team="Boston Celtics",
            market="spread",
            current_odds=130.0,
            implied_prob=0.43,
            features=features,
        )
        session.add(bet)
        fetched = session.query(Bet).filter_by(selection_id="SEL_002").first()
        assert fetched.features["injury_status"] == "ACTIVE"
        assert fetched.features["is_home"] is True
        assert fetched.features["team_pace"] == pytest.approx(105.3)
        assert fetched.features["recent_form"] == [1, 0, 1, 1, 0]

    def test_json_confidence_interval_round_trip(self, session, game):
        ci = {"p05": 0.51, "p95": 0.73}
        bet = Bet(
            selection_id="SEL_003",
            sport="NBA",
            game_id=game.id,
            team="Los Angeles Lakers",
            market="total",
            current_odds=-110.0,
            implied_prob=0.524,
            confidence_interval=ci,
        )
        session.add(bet)
        fetched = session.query(Bet).filter_by(selection_id="SEL_003").first()
        assert fetched.confidence_interval["p05"] == pytest.approx(0.51)
        assert fetched.confidence_interval["p95"] == pytest.approx(0.73)

    def test_created_at_auto_populated(self, session, game):
        bet = Bet(
            selection_id="SEL_004",
            sport="NBA",
            game_id=game.id,
            team="Los Angeles Lakers",
            market="moneyline",
            current_odds=-150.0,
            implied_prob=0.60,
        )
        session.add(bet)
        session.flush()
        assert bet.created_at is not None
        assert isinstance(bet.created_at, datetime.datetime)

    def test_optional_fields_are_nullable(self, session, game):
        bet = Bet(
            selection_id="SEL_005",
            sport="NBA",
            game_id=game.id,
            team="Los Angeles Lakers",
            market="spread",
            current_odds=-110.0,
            implied_prob=0.524,
        )
        session.add(bet)
        fetched = session.query(Bet).filter_by(selection_id="SEL_005").first()
        # Fields not set should be None
        assert fetched.posterior_prob is None
        assert fetched.edge is None
        assert fetched.kelly_fraction is None
        assert fetched.features is None

    def test_selection_id_unique(self, session, game):
        from sqlalchemy.exc import IntegrityError
        bet1 = Bet(
            selection_id="SEL_DUP",
            sport="NBA",
            game_id=game.id,
            team="Los Angeles Lakers",
            market="moneyline",
            current_odds=-150.0,
            implied_prob=0.60,
        )
        session.add(bet1)

        bet2 = Bet(
            selection_id="SEL_DUP",
            sport="NBA",
            game_id=game.id,
            team="Boston Celtics",
            market="moneyline",
            current_odds=130.0,
            implied_prob=0.43,
        )
        session.add(bet2)
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()

    def test_game_relationship_accessible(self, session, game):
        bet = Bet(
            selection_id="SEL_REL",
            sport="NBA",
            game_id=game.id,
            team="Los Angeles Lakers",
            market="moneyline",
            current_odds=-150.0,
            implied_prob=0.60,
        )
        session.add(bet)
        fetched = session.query(Bet).filter_by(selection_id="SEL_REL").first()
        assert fetched.game is not None
        assert fetched.game.sport == "NBA"

    def test_multiple_bets_per_game(self, session, game):
        for i, market in enumerate(["moneyline", "spread", "total"]):
            bet = Bet(
                selection_id=f"SEL_MULTI_{i}",
                sport="NBA",
                game_id=game.id,
                team="Los Angeles Lakers",
                market=market,
                current_odds=-110.0,
                implied_prob=0.524,
            )
            session.add(bet)

        fetched_game = session.get(Game, game.id)
        assert len(fetched_game.bets) >= 3
