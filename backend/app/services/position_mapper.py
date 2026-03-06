"""
Player Position Mapping Service

Maps NBA players to their primary positions (PG/SG/SF/PF/C) for DvP analysis.
Uses a multi-strategy approach: NBAStatsService API → stat-based inference → fallback.
"""

from typing import Optional, Dict
from loguru import logger
from app.services.nba_stats_service import NBAStatsService


# Team abbreviation normalization (DvP sources vs internal)
TEAM_ABBREV_MAP = {
    'NY': 'NYK',
    'NO': 'NOP',
    'SA': 'SAS',
    'GS': 'GSW',
    'UTH': 'UTA',
}


class PositionMapper:
    """Maps players to positions and normalizes team abbreviations"""

    def __init__(self):
        self.nba_stats = NBAStatsService()
        self._position_cache: Dict[str, str] = {}

    def normalize_team_abbrev(self, team: str) -> str:
        """
        Normalize team abbreviation to internal format.
        
        Args:
            team: Team abbreviation (may be DvP format or internal)
            
        Returns:
            Normalized team abbreviation
        """
        return TEAM_ABBREV_MAP.get(team, team)

    def get_player_position(
        self, player_name: str, stat_type: Optional[str] = None
    ) -> str:
        """
        Get player's primary position.
        
        Args:
            player_name: Player's full name
            stat_type: Optional stat type hint (e.g., 'pts', 'reb', 'ast')
            
        Returns:
            Position code: PG, SG, SF, PF, or C
        """
        
        # Check cache
        if player_name in self._position_cache:
            return self._position_cache[player_name]

        # Strategy 1: Try NBAStatsService API
        try:
            player_info = self.nba_stats.get_player_info(player_name)
            if player_info and 'position' in player_info:
                pos = self._normalize_position(player_info['position'])
                if pos:
                    self._position_cache[player_name] = pos
                    logger.debug(f"Position from API: {player_name} → {pos}")
                    return pos
        except Exception as e:
            logger.debug(f"API position lookup failed for {player_name}: {e}")

        # Strategy 2: Infer from stat type
        if stat_type:
            inferred_pos = self._infer_position_from_stat(stat_type)
            self._position_cache[player_name] = inferred_pos
            logger.debug(f"Position inferred from stat: {player_name} → {inferred_pos} (stat: {stat_type})")
            return inferred_pos

        # Strategy 3: Default fallback
        default_pos = 'SF'  # Most neutral position
        self._position_cache[player_name] = default_pos
        logger.debug(f"Position defaulted: {player_name} → {default_pos}")
        return default_pos

    def _normalize_position(self, position: str) -> Optional[str]:
        """
        Normalize position string to standard codes (PG/SG/SF/PF/C).
        
        Handles variations like:
        - "Point Guard" → "PG"
        - "G" → "SG" (default guard)
        - "F-C" → "PF" (hybrid forward-center)
        """
        
        pos_upper = position.upper().strip()
        
        # Direct mappings
        if pos_upper in ['PG', 'SG', 'SF', 'PF', 'C']:
            return pos_upper
        
        # Full position names
        position_map = {
            'POINT GUARD': 'PG',
            'SHOOTING GUARD': 'SG',
            'SMALL FORWARD': 'SF',
            'POWER FORWARD': 'PF',
            'CENTER': 'C',
        }
        if pos_upper in position_map:
            return position_map[pos_upper]
        
        # Single letter codes (G, F)
        if pos_upper == 'G':
            return 'SG'  # Default guard
        if pos_upper == 'F':
            return 'SF'  # Default forward
        
        # Hybrid positions (G-F, F-C, etc.)
        if '-' in pos_upper:
            parts = pos_upper.split('-')
            # Return first position
            if 'G' in parts[0]:
                return 'SG'
            if 'F' in parts[0]:
                return 'SF'
            if 'C' in parts[0]:
                return 'C'
        
        return None

    def _infer_position_from_stat(self, stat_type: str) -> str:
        """
        Infer position from stat type.
        
        Logic:
        - Assists → guards (PG/SG)
        - Rebounds/blocks → bigs (PF/C)
        - Steals/3PM → wings (SG/SF)
        - Points → neutral (SF)
        """
        
        stat_lower = stat_type.lower()
        
        if 'ast' in stat_lower or 'assist' in stat_lower:
            return 'PG'
        
        if 'reb' in stat_lower or 'rebound' in stat_lower:
            return 'PF'
        
        if 'blk' in stat_lower or 'block' in stat_lower:
            return 'C'
        
        if 'stl' in stat_lower or 'steal' in stat_lower:
            return 'SG'
        
        if '3p' in stat_lower or 'three' in stat_lower:
            return 'SG'
        
        # Default: neutral position
        return 'SF'

    def clear_cache(self):
        """Clear the position cache (useful for testing)"""
        self._position_cache.clear()
