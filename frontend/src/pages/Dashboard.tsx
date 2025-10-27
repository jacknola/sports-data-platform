import { useQuery } from '@tanstack/react-query'
import { TrendingUp, Zap, AlertCircle, CheckCircle2, Bot } from 'lucide-react'
import { api } from '../utils/api'
import ActionCard from '../components/ActionCard'
import AgentStatus from '../components/AgentStatus'
import QuickStats from '../components/QuickStats'

export default function Dashboard() {
  const { data: agentStatus, isLoading: agentsLoading } = useQuery({
    queryKey: ['agent-status'],
    queryFn: () => api.get('/api/v1/agents/status'),
  })
  
  const { data: betsResponse, isLoading: betsLoading } = useQuery({
    queryKey: ['best-bets'],
    queryFn: async () => {
      const response = await api.get('/api/v1/bets?store_data=true')
      return response.data
    },
  })
  
  const bets = betsResponse?.bets || []
  
  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-600 mt-1">AI-powered sports intelligence</p>
        </div>
        <button className="btn-primary flex items-center gap-2">
          <Zap className="w-4 h-4" />
          Run Analysis
        </button>
      </div>
      
      {/* Quick Stats */}
      <QuickStats data={agentStatus} />
      
      {/* Action Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <ActionCard
          icon={TrendingUp}
          title="Best Bets"
          description="Top value opportunities"
          count={bets?.length || 0}
          color="primary"
          href="/bets"
        />
        <ActionCard
          icon={Bot}
          title="AI Agents"
          description="System monitoring"
          count={5}
          color="accent"
          href="/agents"
        />
        <ActionCard
          icon={AlertCircle}
          title="Alerts"
          description="Important updates"
          count={3}
          color="warning"
          href="/analysis"
        />
      </div>
      
      {/* Agent Status */}
      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Agent Status</h2>
        <div className="card">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            {agentStatus?.agents && Object.entries(agentStatus.agents).map(([name, data]: [string, any]) => (
              <AgentStatus key={name} name={name} data={data} />
            ))}
          </div>
        </div>
      </div>
      
      {/* Recent Bets */}
      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Recent Best Bets</h2>
        <div className="card">
          <div className="space-y-4">
            {betsLoading ? (
              <div className="text-center py-8 text-gray-500">Loading bets...</div>
            ) : bets && bets.length > 0 ? (
              bets.slice(0, 5).map((bet: any, idx: number) => (
                <div key={idx} className="flex items-center justify-between py-3 border-b last:border-0">
                  <div>
                    <div className="font-semibold text-gray-900">
                      {bet.selection || bet.team} - {bet.market}
                    </div>
                    <div className="text-sm text-gray-500">
                      {bet.sport} • {typeof bet.game === 'string' ? bet.game : 
                        bet.game?.away_team && bet.game?.home_team ? 
                        `${bet.game.away_team} @ ${bet.game.home_team}` : 
                        'Game Info'}
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <div className="text-sm font-semibold text-green-600">
                        +{(bet.edge * 100).toFixed(1)}% edge
                      </div>
                      <div className="text-xs text-gray-500">
                        {bet.current_odds > 0 ? `+${bet.current_odds}` : bet.current_odds}
                      </div>
                    </div>
                    <CheckCircle2 className="w-5 h-5 text-green-500" />
                  </div>
                </div>
              ))
            ) : (
              <div className="text-center py-8 text-gray-500">No bets available</div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

