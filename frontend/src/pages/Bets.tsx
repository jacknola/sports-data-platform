import { useQuery } from '@tanstack/react-query'
import { TrendingUp, Target, AlertCircle, CheckCircle2, DollarSign } from 'lucide-react'
import { api } from '../utils/api'

export default function Bets() {
  const { data: bets, isLoading } = useQuery({
    queryKey: ['best-bets'],
    queryFn: () => api.get('/api/v1/bets'),
  })
  
  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Best Bets</h1>
          <p className="text-gray-600 mt-1">AI-identified value opportunities</p>
        </div>
        <button className="btn-primary flex items-center gap-2">
          <Target className="w-4 h-4" />
          Analyze Today's Games
        </button>
      </div>
      
      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="card">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
              <TrendingUp className="w-6 h-6 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-600">Total Bets</p>
              <p className="text-2xl font-bold text-gray-900">{bets?.length || 0}</p>
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
              <Target className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-gray-600">Value Bets</p>
              <p className="text-2xl font-bold text-gray-900">
                {bets?.filter((b: any) => b.edge > 0.05).length || 0}
              </p>
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
              <DollarSign className="w-6 h-6 text-purple-600" />
            </div>
            <div>
              <p className="text-sm text-gray-600">Avg Edge</p>
              <p className="text-2xl font-bold text-gray-900">
                {bets?.length ? (bets.reduce((sum: number, b: any) => sum + b.edge, 0) / bets.length * 100).toFixed(1) + '%' : '0%'}
              </p>
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
              <CheckCircle2 className="w-6 h-6 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-600">Win Rate</p>
              <p className="text-2xl font-bold text-gray-900">72%</p>
            </div>
          </div>
        </div>
      </div>
      
      {/* Bets List */}
      <div className="card">
        {isLoading ? (
          <div className="text-center py-12 text-gray-500">Loading bets...</div>
        ) : bets && bets.length > 0 ? (
          <div className="space-y-4">
            {bets.map((bet: any, idx: number) => (
              <div key={idx} className="border border-gray-200 rounded-lg p-6 hover:border-primary-300 transition-colors">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-lg font-bold text-gray-900">{bet.description}</h3>
                      <span className="badge badge-success">{bet.sport}</span>
                    </div>
                    <p className="text-sm text-gray-600">Selection ID: {bet.selection_id}</p>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-bold text-green-600">+{bet.edge * 100}%</div>
                    <div className="text-sm text-gray-500">Edge</div>
                  </div>
                </div>
                
                <div className="grid grid-cols-3 gap-4 pt-4 border-t border-gray-200">
                  <div>
                    <p className="text-xs text-gray-500 mb-1">Probability</p>
                    <p className="text-lg font-semibold text-gray-900">{(bet.probability * 100).toFixed(1)}%</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-1">Odds</p>
                    <p className="text-lg font-semibold text-gray-900">{bet.current_odds}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-1">Fair Odds</p>
                    <p className="text-lg font-semibold text-gray-900">{bet.fair_american_odds}</p>
                  </div>
                </div>
                
                <div className="flex items-center gap-2 mt-4">
                  {bet.edge > 0.1 ? (
                    <AlertCircle className="w-4 h-4 text-yellow-600" />
                  ) : null}
                  <span className="text-xs text-gray-600">
                    {bet.edge > 0.1 ? 'High value bet - consider larger stake' : 'Solid value bet'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-12">
            <AlertCircle className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600">No bets available</p>
            <button className="btn-primary mt-4">Run Analysis</button>
          </div>
        )}
      </div>
    </div>
  )
}

