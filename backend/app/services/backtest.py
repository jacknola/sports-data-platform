"""
Backtesting and calibration service for prediction evaluation
"""
from typing import List, Dict, Any, Optional
import numpy as np
from loguru import logger

try:
    from sklearn.metrics import roc_auc_score
    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False


class BacktestService:
    """Evaluate probabilistic predictions with proper scoring and calibration."""

    def __init__(self) -> None:
        pass

    def evaluate(self, predictions: List[Dict[str, Any]], bins: int = 10) -> Dict[str, Any]:
        """
        Evaluate predictions.

        Each item should contain:
        - y_true: 0/1 or bool actual outcome for the predicted event
        - p: predicted probability in [0, 1]
        Optional for ROI:
        - bet: whether a bet was placed (bool)
        - american_odds: int (e.g., -110, +150)
        - stake: float (defaults to 1)
        - edge: optional float
        """
        if not predictions:
            return {
                "count": 0,
                "log_loss": None,
                "brier": None,
                "auc": None,
                "ece": None,
                "calibration": [],
                "roi": None,
                "total_staked": 0.0,
                "total_profit": 0.0,
            }

        y_list: List[float] = []
        p_list: List[float] = []

        for item in predictions:
            y = item.get("y_true")
            p = item.get("p")
            if isinstance(y, bool):
                y = 1.0 if y else 0.0
            if y is None or p is None:
                continue
            # Clamp probabilities to avoid log(0)
            p = max(1e-15, min(1 - 1e-15, float(p)))
            y_list.append(float(y))
            p_list.append(float(p))

        n = len(y_list)
        if n == 0:
            return {
                "count": 0,
                "log_loss": None,
                "brier": None,
                "auc": None,
                "ece": None,
                "calibration": [],
                "roi": None,
                "total_staked": 0.0,
                "total_profit": 0.0,
            }

        y_arr = np.array(y_list, dtype=float)
        p_arr = np.array(p_list, dtype=float)

        # Proper scoring rules
        log_loss = float(-np.mean(y_arr * np.log(p_arr) + (1 - y_arr) * np.log(1 - p_arr)))
        brier = float(np.mean((p_arr - y_arr) ** 2))

        # AUC
        auc: Optional[float] = None
        if SKLEARN_AVAILABLE and len({0.0, 1.0}.intersection(set(y_arr))) == 2:
            try:
                auc = float(roc_auc_score(y_arr, p_arr))
            except Exception:
                auc = None

        # Calibration curve and ECE
        bin_edges = np.linspace(0.0, 1.0, bins + 1)
        bin_ids = np.digitize(p_arr, bin_edges, right=True)
        calibration: List[Dict[str, Any]] = []
        ece = 0.0
        for b in range(1, bins + 1):
            mask = bin_ids == b
            count_b = int(np.sum(mask))
            if count_b == 0:
                calibration.append({
                    "bin": b,
                    "count": 0,
                    "avg_pred": None,
                    "empirical": None,
                    "lower": float(bin_edges[b-1]),
                    "upper": float(bin_edges[b]),
                })
                continue
            avg_pred = float(np.mean(p_arr[mask]))
            empirical = float(np.mean(y_arr[mask]))
            weight = count_b / n
            ece += weight * abs(empirical - avg_pred)
            calibration.append({
                "bin": b,
                "count": count_b,
                "avg_pred": avg_pred,
                "empirical": empirical,
                "lower": float(bin_edges[b-1]),
                "upper": float(bin_edges[b]),
            })

        # ROI for placed bets
        def american_to_decimal(odds: float) -> float:
            return (odds / 100.0 + 1.0) if odds > 0 else (100.0 / abs(odds) + 1.0)

        total_staked = 0.0
        total_profit = 0.0
        num_bets = 0
        edges: List[float] = []

        for item in predictions:
            if not item.get("bet"):
                continue
            american = item.get("american_odds")
            if american is None:
                continue
            stake = float(item.get("stake", 1.0))
            y = item.get("y_true")
            if isinstance(y, bool):
                y = 1.0 if y else 0.0
            if y is None:
                continue
            dec = american_to_decimal(float(american))
            profit = (dec - 1.0) * stake if y == 1.0 else -stake
            total_profit += profit
            total_staked += stake
            num_bets += 1
            if "edge" in item and item["edge"] is not None:
                try:
                    edges.append(float(item["edge"]))
                except Exception:
                    pass

        roi = None
        if total_staked > 0:
            roi = float(total_profit / total_staked)

        avg_edge = float(np.mean(edges)) if edges else None

        result = {
            "count": n,
            "log_loss": round(log_loss, 6),
            "brier": round(brier, 6),
            "auc": round(auc, 6) if auc is not None else None,
            "ece": round(float(ece), 6),
            "calibration": calibration,
            "roi": roi if roi is None else round(roi, 6),
            "total_staked": round(total_staked, 6),
            "total_profit": round(total_profit, 6),
            "num_bets": num_bets,
            "avg_edge": round(avg_edge, 6) if avg_edge is not None else None,
        }

        logger.info(
            f"Backtest: n={n}, log_loss={result['log_loss']}, brier={result['brier']}, auc={result['auc']}, ece={result['ece']}, roi={result['roi']}"
        )
        return result
