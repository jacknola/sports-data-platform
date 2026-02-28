export interface AgentData {
  id?: string
  total_executions?: number
  total_mistakes?: number
  mistake_rate?: number
  recent_mistakes?: Array<{ type: string; error?: string }>
}

export interface AgentStatusResponse {
  agents?: Record<string, AgentData>
}

export interface BetItem {
  description?: string
  sport?: string
  selection_id?: string
  edge: number
  probability: number
  current_odds?: string
  fair_american_odds?: string
  game?: string
  market?: string
}

// Parlay types
export interface ParlayLeg {
  id?: string
  parlay_id?: string
  game_id?: string
  team?: string
  opponent?: string
  pick?: string
  market?: string
  line?: number
  odds?: number
  reasoning?: string
  confidence?: number
  result?: string
  game_time?: string
}

export interface Parlay {
  parlay_id: string
  title?: string
  sport?: string
  confidence_level?: 'LOW' | 'MEDIUM' | 'HIGH' | 'MAX'
  confidence_score?: number
  legs?: ParlayLeg[]
  total_odds?: number
  potential_payout_multiplier?: number
  suggested_unit_size?: number
  analysis?: string
  key_factors?: string[]
  risks?: string[]
  status?: 'pending' | 'won' | 'lost' | 'partial'
  result?: Record<string, unknown>
  actual_return?: number
  profit_loss?: number
  roi?: number
  twitter_post_id?: string
  twitter_posted_at?: string
  tweet_text?: string
  tags?: string[]
  created_at?: string
  updated_at?: string
  event_date?: string
}

export interface ParlayInsights {
  parlay_id: string
  similar_parlays_found: number
  historical_win_rate: number
  similar_parlays: Array<{
    id: string
    similarity: number
    title?: string
    sport?: string
    confidence_level?: string
    status?: string
    result?: string
  }>
  recommendation?: string
  risk_factors?: string[]
}

export interface ParlayStats {
  total_parlays: number
  pending?: number
  won: number
  lost: number
  partial?: number
  win_rate: number
  overall_roi: number
  net_profit: number
  avg_confidence?: number
}
