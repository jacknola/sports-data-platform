"""
Sharp Signal Metrics

Tracks and reports data quality metrics for sharp money signals.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from collections import defaultdict

from loguru import logger

from app.models.sharp_signals import DataQuality, DataSource


class SharpSignalMetrics:
    """
    Tracks data quality metrics for sharp money signals.

    Records:
    - Signals by quality level
    - Signals by data source
    - Data freshness distribution
    - Validation errors and warnings
    """

    def __init__(self):
        self._signal_log: List[Dict[str, Any]] = []
        self._quality_counts: Dict[DataQuality, int] = defaultdict(int)
        self._source_counts: Dict[DataSource, int] = defaultdict(int)
        self._daily_stats: Dict[str, Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

    def record_signal(
        self,
        signal_type: str,
        quality: DataQuality,
        source: DataSource,
        confidence: float,
        game_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Record a generated signal with its quality metrics."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "signal_type": signal_type,
            "quality": quality.value,
            "source": source.value,
            "confidence": confidence,
            "game_id": game_id,
            "metadata": metadata or {},
        }

        self._signal_log.append(entry)
        self._quality_counts[quality] += 1
        self._source_counts[source] += 1

        # Daily aggregation
        day_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._daily_stats[day_key]["total"] += 1
        self._daily_stats[day_key][quality.value] += 1
        self._daily_stats[day_key][source.value] += 1

        if len(self._signal_log) > 10000:
            # Keep last 10k signals to prevent memory bloat
            self._signal_log = self._signal_log[-5000:]

    def record_data_source(
        self,
        source: DataSource,
        success: bool,
        latency_ms: Optional[float] = None,
        error: Optional[str] = None,
    ) -> None:
        """Record data source fetch attempt."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source.value,
            "success": success,
            "latency_ms": latency_ms,
            "error": error,
        }

        logger.debug(f"Data source fetch: {entry}")

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics of signal quality."""
        total_signals = sum(self._quality_counts.values())

        if total_signals == 0:
            return {"total_signals": 0, "message": "No signals recorded yet"}

        quality_breakdown = {
            quality.value: {
                "count": count,
                "percentage": round(count / total_signals * 100, 2),
            }
            for quality, count in self._quality_counts.items()
        }

        source_breakdown = {
            source.value: {
                "count": count,
                "percentage": round(count / total_signals * 100, 2),
            }
            for source, count in self._source_counts.items()
        }

        production_ready_count = self._quality_counts.get(
            DataQuality.LIVE, 0
        ) + self._quality_counts.get(DataQuality.INFERRED, 0)
        mock_count = self._quality_counts.get(DataQuality.MOCK, 0)

        return {
            "total_signals": total_signals,
            "quality_breakdown": quality_breakdown,
            "source_breakdown": source_breakdown,
            "production_ready_percentage": round(
                production_ready_count / total_signals * 100, 2
            ),
            "mock_data_percentage": round(mock_count / total_signals * 100, 2),
            "daily_stats": dict(self._daily_stats),
            "recent_signals": self._signal_log[-50:],
        }

    def get_quality_report(self) -> str:
        """Generate a human-readable quality report."""
        stats = self.get_summary_stats()

        if stats["total_signals"] == 0:
            return "No signals recorded yet."

        report_lines = [
            "=" * 50,
            "SHARP SIGNAL DATA QUALITY REPORT",
            "=" * 50,
            f"Total Signals: {stats['total_signals']}",
            f"Production Ready: {stats['production_ready_percentage']}%",
            f"Mock Data: {stats['mock_data_percentage']}%",
            "",
            "QUALITY BREAKDOWN:",
            "-" * 30,
        ]

        for quality, data in stats["quality_breakdown"].items():
            report_lines.append(f"  {quality}: {data['count']} ({data['percentage']}%)")

        report_lines.extend(["", "SOURCE BREAKDOWN:", "-" * 30])

        for source, data in stats["source_breakdown"].items():
            report_lines.append(f"  {source}: {data['count']} ({data['percentage']}%)")

        report_lines.append("=" * 50)

        return "\n".join(report_lines)

    def reset(self) -> None:
        """Reset all metrics (useful for testing)."""
        self._signal_log.clear()
        self._quality_counts.clear()
        self._source_counts.clear()
        self._daily_stats.clear()
        logger.info("Sharp signal metrics reset")
