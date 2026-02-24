"""
Unit tests for PlayerGameLog model.
"""
import pytest
from datetime import datetime, timezone
from app.models.player_game_log import PlayerGameLog

def test_create_player_game_log(db_session):
    log = PlayerGameLog(
        external_log_id="NBA_LOG_MODEL_TEST",
        game_date=datetime.now(timezone.utc),
        pts=25,
        reb=10,
        ast=5,
        pra=40
    )
    db_session.add(log)
    db_session.commit()
    
    saved = db_session.query(PlayerGameLog).filter_by(external_log_id="NBA_LOG_MODEL_TEST").first()
    assert saved is not None
    assert saved.pts == 25
    assert saved.pra == 40
