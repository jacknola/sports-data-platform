"""
Bayesian analysis for sports betting
"""
import numpy as np
from scipy import stats
from typing import Dict, Any
from loguru import logger


class BayesianAnalyzer:
    """Bayesian probability calculator for sports betting"""
    
    def compute_posterior(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute Bayesian posterior probability for a betting selection
        
        Args:
            data: Contains devig_prob, implied_prob, features, selection_id
            
        Returns:
            Dictionary with posterior_p, fair_american_odds, edge, and confidence interval
        """
        prior_prob = data.get('devig_prob', 0.5)
        implied_prob = data.get('implied_prob', 0.5)
        features = data.get('features', {})
        
        logger.info(f"Computing posterior for selection {data.get('selection_id')}")
        
        # Convert prior to Beta parameters
        prior_strength = 10  # Equivalent sample size
        alpha_prior = prior_prob * prior_strength
        beta_prior = (1 - prior_prob) * prior_strength
        
        # Feature-based adjustments
        adjustments = self._compute_adjustments(features, prior_prob)
        
        # Apply adjustments
        total_adjustment = sum(adjustments.values())
        adjusted_prob = max(0.01, min(0.99, prior_prob + total_adjustment))
        
        # Update Beta parameters with pseudo-observations
        pseudo_obs = 20
        alpha_post = alpha_prior + adjusted_prob * pseudo_obs
        beta_post = beta_prior + (1 - adjusted_prob) * pseudo_obs
        
        # Monte Carlo simulation
        n_simulations = 20000
        samples = np.random.beta(alpha_post, beta_post, n_simulations)
        
        # Calculate statistics
        posterior_p = float(np.mean(samples))
        p05 = float(np.percentile(samples, 5))
        p95 = float(np.percentile(samples, 95))
        
        # Convert to American odds
        fair_american = self._prob_to_american_odds(posterior_p)
        
        # Calculate edge
        edge = posterior_p - implied_prob
        
        result = {
            'selection_id': data.get('selection_id'),
            'prior_prob': round(prior_prob, 4),
            'posterior_p': round(posterior_p, 4),
            'fair_american_odds': round(fair_american, 1),
            'current_american_odds': data.get('current_american_odds'),
            'edge': round(edge, 4),
            'confidence_interval': {
                'p05': round(p05, 4),
                'p95': round(p95, 4)
            },
            'monte_carlo': {
                'n_simulations': n_simulations,
                'mean': round(posterior_p, 4),
                'std': round(float(np.std(samples)), 4)
            },
            'adjustments': adjustments
        }
        
        logger.info(f"Posterior computed: {posterior_p:.4f}, Edge: {edge:.4f}")
        
        return result
    
    def _compute_adjustments(self, features: Dict, prior_prob: float) -> Dict[str, float]:
        """Compute adjustments based on feature values"""
        adjustments = {}
        
        # Injury adjustment
        injury_status = features.get('injury_status', 'ACTIVE')
        if injury_status == 'QUESTIONABLE':
            adjustments['injury'] = -0.05
        elif injury_status == 'OUT':
            adjustments['injury'] = -0.99
        else:
            adjustments['injury'] = 0.0
        
        # Pace adjustment
        team_pace = features.get('team_pace', 0)
        opp_pace = features.get('opponent_pace', 0)
        if team_pace and opp_pace:
            pace_factor = (team_pace + opp_pace) / 2
            league_avg = features.get('league_avg_pace', pace_factor)
            if league_avg > 0:
                pace_delta = (pace_factor - league_avg) / league_avg
                adjustments['pace'] = pace_delta * 0.1
        
        # Usage trend
        usage = features.get('usage', {})
        if usage.get('value'):
            usage_trend = usage.get('trend', 0)
            adjustments['usage'] = usage_trend * 0.02
        
        # Weather impact (for outdoor sports)
        weather = features.get('weather', {})
        if weather.get('type') == 'outdoor':
            wind = weather.get('wind_mph', 0)
            if wind > 20:
                adjustments['weather'] = -0.03
            else:
                adjustments['weather'] = 0.0
        
        # Home/away advantage
        is_home = features.get('is_home', False)
        if is_home:
            adjustments['home_advantage'] = 0.03
        else:
            adjustments['home_advantage'] = -0.03
        
        # Recent form
        recent_form = features.get('recent_form', [])
        if recent_form:
            avg_form = np.mean(recent_form)
            adjustments['form'] = (avg_form - 0.5) * 0.1
        
        return adjustments
    
    def _prob_to_american_odds(self, prob: float) -> float:
        """Convert probability to American odds"""
        if prob > 0.5:
            return -100 * prob / (1 - prob)
        else:
            return 100 * (1 - prob) / prob
    
    def calculate_kelly_criterion(self, prob: float, odds: float) -> float:
        """
        Calculate Kelly Criterion for bet sizing
        
        Args:
            prob: Probability of winning
            odds: Decimal odds
            
        Returns:
            Kelly fraction (percentage of bankroll to bet)
        """
        if odds <= 1:
            return 0.0
        
        kelly = (prob * odds - 1) / (odds - 1)
        return max(0.0, min(kelly, 0.25))  # Cap at 25% of bankroll

