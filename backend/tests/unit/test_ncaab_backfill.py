"""
Unit tests for NCAAB historical data scraper.
"""
from unittest.mock import MagicMock, patch
from app.services.ncaab_backfill import NCAABBackfillService
from app.models.game import Game

def test_scrape_ncaab_historical(db_session):
    # Mock HTML response for a scores page
    mock_html = """
    <div class="game-card">
        <span class="home-team">Duke</span>
        <span class="home-score">80</span>
        <span class="away-team">UNC</span>
        <span class="away-score">75</span>
        <span class="game-date">2024-02-10</span>
    </div>
    """
    
    with patch("app.services.ncaab_backfill.httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.text = mock_html
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp
        
        service = NCAABBackfillService(db_session)
        # Using a dummy URL for the test
        count = service.scrape_from_url("http://example.com/scores")
        
        assert count == 1
        game = db_session.query(Game).filter_by(home_team="Duke").first()
        assert game is not None
        assert game.home_score == 80
        assert game.away_score == 75
