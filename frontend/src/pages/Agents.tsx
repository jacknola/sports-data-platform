import { useQuery } from '@tanstack/react-query'
import { Bot, Activity, AlertCircle, CheckCircle2, Target } from 'lucide-react'
import { api } from '../utils/api'

export default function Agents() {
  const { data: agentStatus, isLoading } = useQuery({
    queryKey: ['agent-status'],
    queryFn: () => api.get('/api/v1/agents/status'),
  })
  
  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">AI Agents</h1>
          <p className="text-gray-600 mt-1">Multi-agent system monitoring</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
          <span className="text-sm font-medium text-gray-900">All Systems Operational</span>
        </div>
      </div>
      
      {/* Overview Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="card">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-primary-100 rounded-lg flex items-center justify-center">
              <Bot className="w-6 h-6 text-primary-600" />
            </div>
            <div>
              <p className="text-sm text-gray-600">Total Agents</p>
              <p className="text-2xl font-bold text-gray-900">5</p>
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
              <Activity className="w-6 h-6 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-600">Active Tasks</p>
              <p className="text-2xl font-bold text-gray-900">
                {agentStatus?.agents ? Object.values(agentStatus.agents).reduce((sum: number, agent: any) => sum + (agent.total_executions || 0), 0) : 0}
              </p>
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-red-100 rounded-lg flex items-center justify-center">
              <AlertCircle className="w-6 h-6 text-red-600" />
            </div>
            <div>
              <p className="text-sm text-gray-600">Mistakes</p>
              <p className="text-2xl font-bold text-gray-900">
                {agentStatus?.agents ? Object.values(agentStatus.agents).reduce((sum: number, agent: any) => sum + (agent.total_mistakes || 0), 0) : 0}
              </p>
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
              <Target className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-gray-600">Success Rate</p>
              <p className="text-2xl font-bold text-gray-900">94.5%</p>
            </div>
          </div>
        </div>
      </div>
      
      {/* Agent Details */}
      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Agent Details</h2>
        <div className="space-y-4">
          {isLoading ? (
            <div className="text-center py-12 text-gray-500">Loading agents...</div>
          ) : agentStatus?.agents ? (
            Object.entries(agentStatus.agents).map(([name, data]: [string, any]) => (
              <div key={name} className="card">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-primary-100 rounded-lg flex items-center justify-center">
                      <Bot className="w-6 h-6 text-primary-600" />
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900 capitalize">{name.replace('Agent', '')}</h3>
                      <p className="text-sm text-gray-600">Agent ID: {data.id}</p>
                    </div>
                  </div>
                  {data.mistake_rate && data.mistake_rate < 0.1 ? (
                    <span className="badge badge-success">Operational</span>
                  ) : data.mistake_rate && data.mistake_rate < 0.3 ? (
                    <span className="badge badge-warning">Monitoring</span>
                  ) : (
                    <span className="badge badge-danger">Needs Attention</span>
                  )}
                </div>
                
                <div className="grid grid-cols-3 gap-4">
                  <div className="p-4 bg-gray-50 rounded-lg">
                    <p className="text-xs text-gray-600 mb-1">Total Executions</p>
                    <p className="text-xl font-bold text-gray-900">{data.total_executions || 0}</p>
                  </div>
                  <div className="p-4 bg-gray-50 rounded-lg">
                    <p className="text-xs text-gray-600 mb-1">Total Mistakes</p>
                    <p className="text-xl font-bold text-red-600">{data.total_mistakes || 0}</p>
                  </div>
                  <div className="p-4 bg-gray-50 rounded-lg">
                    <p className="text-xs text-gray-600 mb-1">Mistake Rate</p>
                    <p className="text-xl font-bold text-gray-900">{((data.mistake_rate || 0) * 100).toFixed(2)}%</p>
                  </div>
                </div>
                
                {data.recent_mistakes && data.recent_mistakes.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-gray-200">
                    <p className="text-sm font-semibold text-gray-900 mb-2">Recent Mistakes</p>
                    <div className="space-y-2">
                      {data.recent_mistakes.slice(0, 3).map((mistake: any, idx: number) => (
                        <div key={idx} className="text-xs text-gray-600 bg-red-50 p-2 rounded">
                          {mistake.type}: {mistake.error || 'Unknown error'}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))
          ) : (
            <div className="text-center py-12 text-gray-500">No agent data available</div>
          )}
        </div>
      </div>
    </div>
  )
}

