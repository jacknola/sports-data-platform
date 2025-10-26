import { CheckCircle2, XCircle, AlertCircle } from 'lucide-react'
import { clsx } from 'clsx'

interface AgentStatusProps {
  name: string
  data: {
    total_executions?: number
    total_mistakes?: number
    mistake_rate?: number
  }
}

export default function AgentStatus({ name, data }: AgentStatusProps) {
  const getStatus = () => {
    const rate = data.mistake_rate || 0
    if (rate < 0.1) return 'operational'
    if (rate < 0.3) return 'warning'
    return 'critical'
  }
  
  const status = getStatus()
  const statusConfig = {
    operational: {
      icon: CheckCircle2,
      color: 'text-green-600',
      bgColor: 'bg-green-50',
      borderColor: 'border-green-200',
    },
    warning: {
      icon: AlertCircle,
      color: 'text-yellow-600',
      bgColor: 'bg-yellow-50',
      borderColor: 'border-yellow-200',
    },
    critical: {
      icon: XCircle,
      color: 'text-red-600',
      bgColor: 'bg-red-50',
      borderColor: 'border-red-200',
    },
  }
  
  const config = statusConfig[status]
  const Icon = config.icon
  
  return (
    <div className={clsx('p-4 rounded-lg border-2', config.bgColor, config.borderColor)}>
      <div className="flex items-center justify-between mb-2">
        <h4 className="font-semibold text-gray-900 text-sm capitalize">{name.replace('Agent', '')}</h4>
        <Icon className={clsx('w-5 h-5', config.color)} />
      </div>
      <div className="space-y-1">
        <div className="flex justify-between text-xs">
          <span className="text-gray-600">Executions:</span>
          <span className="font-semibold text-gray-900">{data.total_executions || 0}</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-gray-600">Mistakes:</span>
          <span className="font-semibold text-red-600">{data.total_mistakes || 0}</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-gray-600">Rate:</span>
          <span className="font-semibold text-gray-900">{((data.mistake_rate || 0) * 100).toFixed(1)}%</span>
        </div>
      </div>
    </div>
  )
}

