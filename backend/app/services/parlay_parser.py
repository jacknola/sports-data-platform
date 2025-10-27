"""
Parse parlay descriptions from tweets, e.g., Dan's AI Sports Picks style.

Assumptions based on common formats:
- Title line may include units and total odds, e.g., "5-Leg Parlay (+650) 0.5u".
- Legs often bullet-listed lines like:
  "- Lakers ML"
  "- Tatum 25+ Pts"
  "- Over 220.5"
We extract market, team/player, selection, and line when present.
"""
from __future__ import annotations

import re
from typing import List, Dict, Any


class ParlayParser:
    title_re = re.compile(r"(?:(\d+)[- ]*Leg)\s+Parlay.*?(?:\(([-+]?\d+)\))?.*?(?:([0-9]*\.?[0-9]+)\s*u)?", re.I)
    odds_re = re.compile(r"\(([+\-]?\d+)\)")
    units_re = re.compile(r"(\d*\.?\d+)\s*u", re.I)

    # Leg patterns
    over_under_re = re.compile(r"^(?:[-*]\s*)?(Over|Under)\s+([0-9]+(?:\.[0-9]+)?)", re.I)
    spread_re = re.compile(r"^(?:[-*]\s*)?([A-Za-z .'-]+)\s+([+\-][0-9]+(?:\.[0-9]+)?)$", re.I)
    moneyline_re = re.compile(r"^(?:[-*]\s*)?([A-Za-z .'-]+)\s+ML$", re.I)
    player_thresh_re = re.compile(r"^(?:[-*]\s*)?([A-Za-z .'-]+)\s+(\d+\+?)\s*(Pts|Ast|Reb|3PM|SOG|Shots|Rbs|Assists|Points)\b", re.I)

    def parse(self, text: str) -> Dict[str, Any]:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if not lines:
            return {"legs": []}

        title_line = lines[0]
        num_legs, total_odds, units = self._parse_title(title_line)

        leg_lines = [l for l in lines[1:] if l and not l.lower().startswith("unit")]
        legs = []
        for idx, line in enumerate(leg_lines):
            parsed = self._parse_leg(line)
            if parsed:
                parsed["order_index"] = idx
                legs.append(parsed)

        return {
            "title": title_line,
            "num_legs": num_legs or len(legs),
            "total_odds_american": total_odds,
            "stake_units": units,
            "legs": legs,
        }

    def _parse_title(self, title: str):
        m = self.title_re.search(title)
        if not m:
            odds = self._extract_odds(title)
            units = self._extract_units(title)
            return None, odds, units
        num_legs = int(m.group(1)) if m.group(1) else None
        total_odds = int(m.group(2)) if m.group(2) else self._extract_odds(title)
        units = float(m.group(3)) if m.group(3) else self._extract_units(title)
        return num_legs, total_odds, units

    def _extract_odds(self, s: str):
        m = self.odds_re.search(s)
        return int(m.group(1)) if m else None

    def _extract_units(self, s: str):
        m = self.units_re.search(s)
        return float(m.group(1)) if m else None

    def _parse_leg(self, line: str) -> Dict[str, Any] | None:
        # Over/Under market
        m = self.over_under_re.match(line)
        if m:
            selection = m.group(1).capitalize()
            line_val = float(m.group(2))
            return {"market": "total", "selection": selection, "line": line_val}

        # Moneyline
        m = self.moneyline_re.match(line)
        if m:
            team = m.group(1).strip()
            return {"market": "moneyline", "team": team, "selection": "ML"}

        # Spread
        m = self.spread_re.match(line)
        if m:
            team = m.group(1).strip()
            sel = m.group(2)
            return {"market": "spread", "team": team, "selection": sel}

        # Player thresholds like "Tatum 25+ Pts"
        m = self.player_thresh_re.match(line)
        if m:
            player = m.group(1).strip()
            threshold = m.group(2)
            stat = m.group(3).lower()
            return {
                "market": f"player_{stat}",
                "player": player,
                "selection": threshold,
            }

        # Fallback: try to split by dash or colon
        if " - " in line:
            left, right = line.split(" - ", 1)
            return {"market": "unknown", "team": left.strip(), "selection": right.strip()}

        return None
