"""
ML predictions endpoints

POST /api/v1/analyze-prop  — NBA player prop: RF + Bayesian inference
"""
from fastapi import APIRouter, HTTPException
from loguru import logger

from app.services.inference_service import PropInferenceService
from app.schemas.predict import PropPredictionRequest, PropPredictionResponse

router = APIRouter()
inference_service = PropInferenceService()


@router.post("/analyze-prop", response_model=PropPredictionResponse)
async def analyze_prop(request: PropPredictionRequest) -> PropPredictionResponse:
    """
    NBA player prop inference: Random Forest + Bayesian posterior.

    Steps
    ─────
    1. Scale + weight the 10 features with the persisted StandardScaler
    2. Retrieve the 50 most similar historical contexts from Qdrant
       (pass date_limit to prevent data leakage during backtesting)
    3. Binarise neighbours against prop_line → OVER/UNDER labels
    4. Train a localised Random Forest on those 50 outcomes → rf_prob
    5. Exact Beta-Binomial Bayesian update → posterior_mean + 95% HDI
    6. edge = posterior_mean − implied_prob
    7. Fractional Quarter-Kelly bet sizing

    Returns rf_prob, posterior_mean, edge, HDI, kelly_fraction,
    recommendation (OVER / UNDER / PASS), and neighbour diagnostics.
    """
    features = {
        "usage_rate_season":  request.usage_rate_season,
        "l5_form_variance":   request.l5_form_variance,
        "expected_mins":      request.expected_mins,
        "opp_pace":           request.opp_pace,
        "opp_def_rtg":        request.opp_def_rtg,
        "def_vs_position":    request.def_vs_position,
        "implied_team_total": request.implied_team_total,
        "spread":             request.spread,
        "rest_advantage":     request.rest_advantage,
        "is_home":            float(request.is_home),
    }

    try:
        result = inference_service.predict(
            features=features,
            prop_line=request.prop_line,
            implied_prob=request.implied_prob,
            date_limit=request.date_limit,
        )
        return PropPredictionResponse(**result)

    except ValueError as exc:
        # Not enough Qdrant neighbours — collection needs to be populated
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        # Scaler not found — run sync_qdrant.py first
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error(f"analyze-prop error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
