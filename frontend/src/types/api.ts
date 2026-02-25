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
