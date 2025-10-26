import { TrendingUp, Bot, DollarSign, Target } from 'lucide-react'

interface QuickStatsProps {
  data?: {
    agents?: {
      [key: string]: {
        total_executions?: number
        total_mistakes?: number
      }
    }
  }
}

export default function QuickStats({ data }: QuickStatsProps) {
  const stats = [
    {
      label: 'Total Executions',
      value: data?.agents ? Object.values(data.agents).reduce((sum: number, agent: any) => sum + (agent.total_executions || 0), 0) : 0,
      icon: Bot,
      color: 'primary',
    },
    {
      label: 'Success Rate',
      value: '94.5%',
      icon: Target,
      color: 'success',
    },
    {
      label: 'Best Bets',
      value: '12',
      icon: TrendingUp,
      color: 'accent',
    },
    {
      label: 'Avg Edge',
      value: '+8.2%',
      icon: DollarSign,
      color: 'warning',
    },
  ]
  
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {stats.map((stat, idx) => {
        const Icon = stat.icon
        return (
          <div key={idx} className="card card-hover">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">{stat.label}</p>
                <p className="text-3xl font-bold text-gray-900">{stat.value}</p>
              </div>
              <div className="w-12 h-12 bg-primary-50 rounded-lg flex items-center justify-center">
                <Icon className="w-6 h-6 text-primary-600" />
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

