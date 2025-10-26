import { LucideIcon } from 'lucide-react'
import { Link } from 'react-router-dom'
import { clsx } from 'clsx'

interface ActionCardProps {
  icon: LucideIcon
  title: string
  description: string
  count: number
  color: 'primary' | 'accent' | 'warning' | 'success'
  href: string
}

const colorClasses = {
  primary: 'bg-primary-50 border-primary-200 text-primary-700',
  accent: 'bg-accent-50 border-accent-200 text-accent-700',
  warning: 'bg-yellow-50 border-yellow-200 text-yellow-700',
  success: 'bg-green-50 border-green-200 text-green-700',
}

const iconColorClasses = {
  primary: 'text-primary-600',
  accent: 'text-accent-600',
  warning: 'text-yellow-600',
  success: 'text-green-600',
}

export default function ActionCard({ 
  icon: Icon, 
  title, 
  description, 
  count, 
  color, 
  href 
}: ActionCardProps) {
  return (
    <Link to={href} className="card card-hover border-2 group">
      <div className={clsx('w-12 h-12 rounded-lg flex items-center justify-center mb-4', colorClasses[color])}>
        <Icon className={clsx('w-6 h-6', iconColorClasses[color])} />
      </div>
      <h3 className="text-lg font-semibold text-gray-900 mb-1">{title}</h3>
      <p className="text-sm text-gray-600 mb-3">{description}</p>
      <div className="flex items-center justify-between">
        <span className="text-2xl font-bold text-gray-900">{count}</span>
        <span className="text-sm text-gray-500 group-hover:text-primary-600 group-hover:translate-x-1 transition-all">
          View →
        </span>
      </div>
    </Link>
  )
}

