import { TrendingUp, Bot, DollarSign, Target, LucideIcon } from 'lucide-react'

interface AgentData {
  total_executions?: number
  total_mistakes?: number
}

interface QuickStatsProps {
  data?: {
    agents?: Record<string, AgentData>
  }
}

interface StatItem {
  label: string
  value: string | number
  icon: LucideIcon
  // color property was present in original but unused in render.
  // Keeping it for future use or mapping.
  color: 'primary' | 'success' | 'accent' | 'warning'
}

export default function QuickStats({ data }: QuickStatsProps) {
  const calculateTotalExecutions = (): number => {
    if (!data?.agents) return 0
    return Object.values(data.agents).reduce(
      (sum, agent) => sum + (agent.total_executions || 0),
      0
    )
  }

  const stats: StatItem[] = [
    {
      label: 'Total Executions',
      value: calculateTotalExecutions(),
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
      {stats.map((stat, idx) => (
        <StatCard key={idx} stat={stat} />
      ))}
    </div>
  )
}

function StatCard({ stat }: { stat: StatItem }) {
  const Icon = stat.icon
  return (
    <div className="card card-hover">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-600 mb-1">{stat.label}</p>
          <p className="text-3xl font-bold text-gray-900">{stat.value}</p>
        </div>
        {/*
          Original code used primary color for all icons regardless of stat.color.
          Preserving this behavior to avoid visual regression.
        */}
        <div className="w-12 h-12 bg-primary-50 rounded-lg flex items-center justify-center">
          <Icon className="w-6 h-6 text-primary-600" />
        </div>
      </div>
    </div>
  )
}
