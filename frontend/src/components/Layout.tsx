import { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  Bot,
  TrendingUp,
  BarChart3,
  Settings,
  Zap,
  Trophy
} from 'lucide-react'
import { clsx } from 'clsx'

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()
  
  const navItems = [
    { path: '/', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/bets', label: 'Best Bets', icon: TrendingUp },
    { path: '/college-basketball', label: 'College Basketball', icon: Trophy },
    { path: '/agents', label: 'Agents', icon: Bot },
    { path: '/analysis', label: 'Analysis', icon: BarChart3 },
    { path: '/settings', label: 'Settings', icon: Settings },
  ]
  
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Sidebar */}
      <div className="fixed inset-y-0 left-0 w-64 bg-white border-r border-gray-200">
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="flex items-center gap-2 px-6 py-6 border-b border-gray-200">
            <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-accent-500 rounded-lg flex items-center justify-center">
              <Zap className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">Sports AI</h1>
              <p className="text-xs text-gray-500">Intelligence Platform</p>
            </div>
          </div>
          
          {/* Navigation */}
          <nav className="flex-1 px-4 py-4 space-y-1">
            {navItems.map((item) => {
              const isActive = location.pathname === item.path
              const Icon = item.icon
              
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={clsx(
                    'flex items-center gap-3 px-4 py-3 rounded-lg transition-colors',
                    isActive
                      ? 'bg-primary-50 text-primary-700 font-semibold'
                      : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                  )}
                >
                  <Icon className={clsx('w-5 h-5', isActive ? 'text-primary-600' : 'text-gray-400')} />
                  <span>{item.label}</span>
                </Link>
              )
            })}
          </nav>
          
          {/* Stats */}
          <div className="px-6 py-4 border-t border-gray-200">
            <div className="text-xs text-gray-500 mb-2">System Status</div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
              <span className="text-sm font-medium text-gray-900">All Systems Operational</span>
            </div>
          </div>
        </div>
      </div>
      
      {/* Main Content */}
      <div className="ml-64">
        <div className="p-8">{children}</div>
      </div>
    </div>
  )
}

