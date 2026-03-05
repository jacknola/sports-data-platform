import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  TrendingUp, Target, AlertCircle, CheckCircle2, DollarSign,
  XCircle, MinusCircle, RefreshCw, ChevronDown, ChevronUp, BarChart2,
} from 'lucide-react'
import { api } from '../utils/api'

interface TrackedBet {
  id: string
  created_at: string
  date: string
  game_id: string
  sport: string
  side: string
  market: string
  odds: number
  line: number
  edge: number
  win_probability: number | null
  bet_size: number
  status: 'pending' | 'won' | 'lost' | 'push' | 'void'
  book: string
  actual_clv: number | null
  settled_at: string | null
}

interface PerformanceMetrics {
  wins: number
  losses: number
  pushes: number
  win_rate: number
  units: number
  roi: number
  total_bets: number
  avg_clv: number | null
  clv_sample_size: number
  pending_bets: number
}

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  won:     'bg-green-100 text-green-800',
  lost:    'bg-red-100 text-red-800',
  push:    'bg-gray-100 text-gray-700',
  void:    'bg-gray-100 text-gray-500',
}

function fmtOdds(odds: number): string {
  if (!odds) return '—'
  return odds > 0 ? `+${odds}` : `${odds}`
}

function fmtPct(v: number): string {
  return `${(v * 100).toFixed(1)}%`
}

export default function Bets() {
  const qc = useQueryClient()
  const [sportFilter, setSportFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  // Tracked bets from the portfolio optimizer
  const { data: tracked, isLoading: trackedLoading } = useQuery<TrackedBet[]>({
    queryKey: ['tracked-bets', sportFilter, statusFilter],
    queryFn: () => api.get('/api/v1/bets/tracked', {
      params: {
        sport: sportFilter !== 'all' ? sportFilter : undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined,
      },
    }),
    refetchInterval: 30_000,
  })

  // Performance metrics
  const { data: perf } = useQuery<PerformanceMetrics>({
    queryKey: ['bets-performance', sportFilter],
    queryFn: () => api.get('/api/v1/bets/performance', {
      params: { sport: sportFilter !== 'all' ? sportFilter : undefined },
    }),
    refetchInterval: 30_000,
  })

  // Settle mutation
  const settleMutation = useMutation({
    mutationFn: ({ id, status, clv }: { id: string; status: string; clv?: number }) =>
      api.post(`/api/v1/bets/${id}/settle`, { status, clv }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tracked-bets'] })
      qc.invalidateQueries({ queryKey: ['bets-performance'] })
    },
  })

  const settle = (id: string, status: string) => {
    if (settleMutation.isPending) return
    settleMutation.mutate({ id, status })
  }

  const roiColor = (roi: number) =>
    roi > 0 ? 'text-green-600' : roi < 0 ? 'text-red-600' : 'text-gray-600'

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Bet Tracker</h1>
          <p className="text-gray-600 mt-1">Record results and monitor model performance</p>
        </div>
        <button
          className="btn-secondary flex items-center gap-2"
          onClick={() => {
            qc.invalidateQueries({ queryKey: ['tracked-bets'] })
            qc.invalidateQueries({ queryKey: ['bets-performance'] })
          }}
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Performance KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
        {[
          { label: 'Pending', value: perf?.pending_bets ?? '—', icon: Target, color: 'text-yellow-600', bg: 'bg-yellow-50' },
          { label: 'Wins', value: perf?.wins ?? '—', icon: CheckCircle2, color: 'text-green-600', bg: 'bg-green-50' },
          { label: 'Losses', value: perf?.losses ?? '—', icon: XCircle, color: 'text-red-600', bg: 'bg-red-50' },
          { label: 'Pushes', value: perf?.pushes ?? '—', icon: MinusCircle, color: 'text-gray-500', bg: 'bg-gray-50' },
          { label: 'Win Rate', value: perf ? fmtPct(perf.win_rate) : '—', icon: BarChart2, color: 'text-blue-600', bg: 'bg-blue-50' },
          {
            label: 'ROI',
            value: perf ? `${(perf.roi * 100).toFixed(1)}%` : '—',
            icon: TrendingUp,
            color: perf ? roiColor(perf.roi) : 'text-gray-600',
            bg: 'bg-purple-50',
          },
          {
            label: 'Units P&L',
            value: perf ? `${perf.units >= 0 ? '+' : ''}${perf.units.toFixed(1)}u` : '—',
            icon: DollarSign,
            color: perf ? roiColor(perf.units) : 'text-gray-600',
            bg: 'bg-indigo-50',
          },
        ].map(({ label, value, icon: Icon, color, bg }) => (
          <div key={label} className="card p-4">
            <div className="flex items-center gap-2 mb-1">
              <div className={`w-8 h-8 ${bg} rounded flex items-center justify-center`}>
                <Icon className={`w-4 h-4 ${color}`} />
              </div>
              <p className="text-xs text-gray-500">{label}</p>
            </div>
            <p className={`text-xl font-bold ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Average CLV banner */}
      {perf?.avg_clv != null && (
        <div className={`rounded-lg px-4 py-3 text-sm font-medium ${perf.avg_clv > 0 ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>
          📊 Average Closing Line Value: {perf.avg_clv > 0 ? '+' : ''}{(perf.avg_clv * 100).toFixed(2)}%
          {' '}({perf.clv_sample_size} settled bets with CLV recorded)
          {perf.avg_clv > 0 ? ' — model is beating closing lines ✓' : ' — model is losing to closing lines ✗'}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-600">Sport:</label>
          <select
            className="text-sm border border-gray-300 rounded px-2 py-1"
            value={sportFilter}
            onChange={e => setSportFilter(e.target.value)}
          >
            {['all', 'ncaab', 'nba', 'nfl'].map(s => (
              <option key={s} value={s}>{s.toUpperCase()}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-600">Status:</label>
          <select
            className="text-sm border border-gray-300 rounded px-2 py-1"
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
          >
            {['all', 'pending', 'won', 'lost', 'push', 'void'].map(s => (
              <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
            ))}
          </select>
        </div>
        <span className="text-sm text-gray-500 ml-auto">
          {tracked?.length ?? 0} bet{tracked?.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Bet List */}
      <div className="card divide-y divide-gray-100">
        {trackedLoading ? (
          <div className="text-center py-12 text-gray-500">Loading tracked bets…</div>
        ) : !tracked || tracked.length === 0 ? (
          <div className="text-center py-12">
            <AlertCircle className="w-12 h-12 text-gray-400 mx-auto mb-3" />
            <p className="text-gray-600 font-medium">No bets found</p>
            <p className="text-sm text-gray-500 mt-1">
              Bets are automatically saved when you run the daily analysis export.
            </p>
          </div>
        ) : (
          tracked.map((bet) => {
            const isExpanded = expandedId === bet.id
            const isPending = bet.status === 'pending'
            return (
              <div key={bet.id} className="px-4 py-4">
                <div className="flex items-start justify-between gap-4">
                  {/* Left: identity */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className={`text-xs font-semibold px-2 py-0.5 rounded-full uppercase ${STATUS_COLORS[bet.status]}`}>
                        {bet.status}
                      </span>
                      <span className="text-xs text-gray-400 uppercase">{bet.sport}</span>
                      <span className="text-xs text-gray-400">{bet.date}</span>
                    </div>
                    <p className="font-semibold text-gray-900 truncate">
                      {bet.side}{' '}
                      <span className="text-gray-500 font-normal">{bet.market}</span>
                      {bet.line ? <span className="text-gray-400 font-normal"> · {bet.line}</span> : null}
                    </p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {fmtOdds(bet.odds)} · Win Prob: {bet.win_probability != null ? fmtPct(bet.win_probability) : '—'} · Edge: {(bet.edge * 100).toFixed(1)}% · Size: {bet.bet_size}u
                      {bet.book ? ` · ${bet.book}` : ''}
                    </p>
                  </div>

                  {/* Right: settle buttons or result */}
                  <div className="flex items-center gap-2 shrink-0">
                    {isPending ? (
                      <>
                        <button
                          onClick={() => settle(bet.id, 'won')}
                          disabled={settleMutation.isPending}
                          className="flex items-center gap-1 px-2 py-1 text-xs bg-green-100 text-green-700 rounded hover:bg-green-200 transition-colors disabled:opacity-50"
                          title="Mark Won"
                        >
                          <CheckCircle2 className="w-3 h-3" /> Won
                        </button>
                        <button
                          onClick={() => settle(bet.id, 'lost')}
                          disabled={settleMutation.isPending}
                          className="flex items-center gap-1 px-2 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200 transition-colors disabled:opacity-50"
                          title="Mark Lost"
                        >
                          <XCircle className="w-3 h-3" /> Lost
                        </button>
                        <button
                          onClick={() => settle(bet.id, 'push')}
                          disabled={settleMutation.isPending}
                          className="flex items-center gap-1 px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded hover:bg-gray-200 transition-colors disabled:opacity-50"
                          title="Mark Push"
                        >
                          <MinusCircle className="w-3 h-3" /> Push
                        </button>
                      </>
                    ) : (
                      <span className={`text-sm font-semibold ${
                        bet.status === 'won' ? 'text-green-600' :
                        bet.status === 'lost' ? 'text-red-500' : 'text-gray-400'
                      }`}>
                        {bet.status === 'won' ? '✓ Won' : bet.status === 'lost' ? '✗ Lost' : '— Push'}
                      </span>
                    )}
                    <button
                      onClick={() => setExpandedId(isExpanded ? null : bet.id)}
                      className="text-gray-400 hover:text-gray-600 p-1"
                    >
                      {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {/* Expanded detail */}
                {isExpanded && (
                  <div className="mt-3 pt-3 border-t border-gray-100 grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                    <div>
                      <p className="text-xs text-gray-400">Game ID</p>
                      <p className="text-gray-700 truncate">{bet.game_id || '—'}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-400">Win Probability</p>
                      <p className={bet.win_probability != null ? (bet.win_probability >= 0.5 ? 'text-green-600' : 'text-yellow-600') : 'text-gray-400'}>
                        {bet.win_probability != null ? fmtPct(bet.win_probability) : 'Not recorded'}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-400">CLV</p>
                      <p className={bet.actual_clv != null ? (bet.actual_clv > 0 ? 'text-green-600' : 'text-red-500') : 'text-gray-400'}>
                        {bet.actual_clv != null ? `${bet.actual_clv > 0 ? '+' : ''}${(bet.actual_clv * 100).toFixed(2)}%` : 'Not recorded'}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-400">Bet ID</p>
                      <p className="text-gray-500 font-mono text-xs truncate">{bet.id}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-400">Settled</p>
                      <p className="text-gray-700">{bet.settled_at ? bet.settled_at.split('T')[0] : '—'}</p>
                    </div>
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
