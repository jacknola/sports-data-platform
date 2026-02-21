import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Activity,
  DollarSign,
  BarChart2,
  ChevronRight,
  RefreshCw,
  Info,
} from 'lucide-react'
import { clsx } from 'clsx'
import api from '../utils/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SharpSignal {
  game_id: string
  home_team: string
  away_team: string
  market: string
  sharp_side: string
  signal_types: string[]
  score: number
  score_label: string
  details: Record<string, any>
  created_at: string
}

interface EdgeBet {
  game_id: string
  home_team: string
  away_team: string
  commence_time: string
  market: string
  side: string
  true_prob: number
  fair_odds: number
  best_available_odds: number
  best_book: string
  edge: number
  ev_per_unit: number
  kelly_fraction: number
  sharp_score: number
  sharp_confirmed: boolean
  sharp_signals: string[][]
  composite_score: number
}

interface DashboardSummary {
  sport: string
  active_games: number
  positive_ev_bets: number
  sharp_signal_count: number
  book_divergence_count: number
  top_signals: SharpSignal[]
  top_games_by_edge: Array<{
    game: string
    best_edge: number
    sharp_books: number
    commence_time: string
  }>
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function edgeColor(edge: number): string {
  if (edge >= 0.06) return 'text-green-600'
  if (edge >= 0.03) return 'text-yellow-600'
  return 'text-gray-600'
}

function edgeBadgeColor(edge: number): string {
  if (edge >= 0.06) return 'bg-green-100 text-green-800'
  if (edge >= 0.03) return 'bg-yellow-100 text-yellow-800'
  return 'bg-gray-100 text-gray-700'
}

function sharpScoreColor(score: number): string {
  if (score >= 3) return 'bg-red-100 text-red-800'
  if (score >= 2) return 'bg-orange-100 text-orange-800'
  if (score >= 1) return 'bg-blue-100 text-blue-800'
  return 'bg-gray-100 text-gray-600'
}

function sharpScoreLabel(score: number): string {
  if (score >= 3) return 'Strong Sharp'
  if (score >= 2) return 'Moderate Sharp'
  if (score >= 1) return 'Weak Sharp'
  return 'No Signal'
}

function formatOdds(odds: number): string {
  if (odds > 0) return `+${odds}`
  return `${odds}`
}

function formatPct(val: number): string {
  return `${(val * 100).toFixed(1)}%`
}

function signalTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    book_divergence: 'Book Divergence',
    line_movement: 'Line Movement',
    reverse_line_movement: 'RLM',
    spread_discrepancy: 'Spread Gap',
    spread_line_movement: 'Spread Move',
  }
  return labels[type] || type
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatCard({
  label,
  value,
  icon: Icon,
  accent,
}: {
  label: string
  value: string | number
  icon: React.ElementType
  accent?: string
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex items-center gap-4">
      <div className={clsx('w-11 h-11 rounded-lg flex items-center justify-center', accent ?? 'bg-primary-50')}>
        <Icon className={clsx('w-5 h-5', accent ? 'text-white' : 'text-primary-600')} />
      </div>
      <div>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        <p className="text-sm text-gray-500">{label}</p>
      </div>
    </div>
  )
}

function SharpSignalCard({ signal }: { signal: SharpSignal }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-3">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-gray-900">
            {signal.away_team} <span className="text-gray-400 font-normal">@</span> {signal.home_team}
          </p>
          <p className="text-xs text-gray-500 mt-0.5 capitalize">{signal.market} market</p>
        </div>
        <span className={clsx('text-xs font-semibold px-2 py-1 rounded-full shrink-0', sharpScoreColor(signal.score))}>
          {sharpScoreLabel(signal.score)}
        </span>
      </div>

      {/* Sharp side */}
      <div className="flex items-center gap-2 text-sm">
        <Activity className="w-4 h-4 text-orange-500 shrink-0" />
        <span className="font-medium text-gray-800">Sharp on:</span>
        <span className="text-orange-700 font-semibold">{signal.sharp_side}</span>
      </div>

      {/* Signal tags */}
      <div className="flex flex-wrap gap-1.5">
        {signal.signal_types.map((t) => (
          <span key={t} className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full font-medium">
            {signalTypeLabel(t)}
          </span>
        ))}
      </div>

      {/* Expand details */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="text-xs text-primary-600 hover:text-primary-800 flex items-center gap-1 font-medium"
      >
        {expanded ? 'Hide details' : 'Show details'}
        <ChevronRight className={clsx('w-3 h-3 transition-transform', expanded && 'rotate-90')} />
      </button>

      {expanded && (
        <div className="bg-gray-50 rounded-lg p-3 space-y-1.5 text-xs">
          {Object.entries(signal.details).map(([key, val]) => {
            if (typeof val === 'object' && val !== null) {
              return (
                <div key={key}>
                  <p className="font-semibold text-gray-700 capitalize">{key.replace(/_/g, ' ')}:</p>
                  {Object.entries(val as Record<string, any>).map(([k2, v2]) => (
                    <p key={k2} className="pl-2 text-gray-600">
                      {k2.replace(/_/g, ' ')}: <span className="font-medium">{String(v2)}</span>
                    </p>
                  ))}
                </div>
              )
            }
            return (
              <p key={key} className="text-gray-600">
                <span className="font-semibold capitalize">{key.replace(/_/g, ' ')}:</span>{' '}
                {String(val)}
              </p>
            )
          })}
        </div>
      )}
    </div>
  )
}

function BestBetRow({ bet, rank }: { bet: EdgeBet; rank: number }) {
  return (
    <tr className="hover:bg-gray-50 transition-colors">
      <td className="py-3 pl-4 pr-3">
        <span className="text-xs text-gray-400 font-medium">#{rank}</span>
      </td>
      <td className="py-3 px-3">
        <p className="text-sm font-semibold text-gray-900 leading-tight">
          {bet.away_team} @ {bet.home_team}
        </p>
        <p className="text-xs text-gray-500 capitalize mt-0.5">{bet.market}</p>
      </td>
      <td className="py-3 px-3">
        <p className="text-sm font-semibold text-gray-800">{bet.side}</p>
        <p className="text-xs text-gray-500 capitalize">{bet.best_book}</p>
      </td>
      <td className="py-3 px-3 text-center">
        <span className="text-sm font-bold text-gray-900">{formatOdds(bet.best_available_odds)}</span>
        <p className="text-xs text-gray-400">fair: {formatOdds(bet.fair_odds)}</p>
      </td>
      <td className="py-3 px-3 text-center">
        <span className={clsx('text-sm font-bold', edgeColor(bet.edge))}>
          {formatPct(bet.edge)}
        </span>
        <p className="text-xs text-gray-400">{formatPct(bet.true_prob)} true</p>
      </td>
      <td className="py-3 px-3 text-center">
        <span className={clsx('text-xs font-semibold px-2 py-1 rounded-full', edgeBadgeColor(bet.edge))}>
          {bet.ev_per_unit >= 0 ? '+' : ''}{(bet.ev_per_unit * 100).toFixed(1)}¢
        </span>
      </td>
      <td className="py-3 px-3 text-center">
        <span className={clsx('text-xs font-semibold px-2 py-1 rounded-full', sharpScoreColor(bet.sharp_score))}>
          {sharpScoreLabel(bet.sharp_score)}
        </span>
      </td>
      <td className="py-3 px-3 text-center text-xs text-gray-500">
        {(bet.kelly_fraction * 100).toFixed(1)}%
      </td>
    </tr>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function CollegeBasketball() {
  const [activeTab, setActiveTab] = useState<'best-bets' | 'sharp-signals' | 'edge'>('best-bets')
  const [minEdge, setMinEdge] = useState(0.02)
  const [minSharpScore, setMinSharpScore] = useState(1)

  // Summary
  const summaryQuery = useQuery<DashboardSummary>({
    queryKey: ['cbb-summary'],
    queryFn: () => api.get('/v1/cbb/summary').then((r) => r.data),
    refetchInterval: 60_000,
  })

  // Best bets
  const bestBetsQuery = useQuery<{ bets: EdgeBet[]; total_best_bets: number }>({
    queryKey: ['cbb-best-bets', minEdge, minSharpScore],
    queryFn: () =>
      api
        .get('/v1/cbb/best-bets', { params: { min_edge: minEdge, min_sharp_score: minSharpScore, limit: 20 } })
        .then((r) => r.data),
    refetchInterval: 90_000,
    enabled: activeTab === 'best-bets',
  })

  // Sharp signals
  const sharpQuery = useQuery<{ signals: SharpSignal[]; total_signals: number }>({
    queryKey: ['cbb-sharp', minSharpScore],
    queryFn: () =>
      api.get('/v1/cbb/sharp', { params: { min_score: minSharpScore } }).then((r) => r.data),
    refetchInterval: 60_000,
    enabled: activeTab === 'sharp-signals',
  })

  // Edge-only view
  const edgeQuery = useQuery<{ bets: EdgeBet[]; total_positive_ev_bets: number }>({
    queryKey: ['cbb-edge', minEdge],
    queryFn: () =>
      api.get('/v1/cbb/edge', { params: { min_edge: minEdge } }).then((r) => r.data),
    refetchInterval: 90_000,
    enabled: activeTab === 'edge',
  })

  const summary = summaryQuery.data
  const isLoading = summaryQuery.isLoading

  const tabs = [
    { id: 'best-bets' as const, label: 'Best Bets', icon: TrendingUp },
    { id: 'sharp-signals' as const, label: 'Sharp Signals', icon: Activity },
    { id: 'edge' as const, label: 'Edge Calculator', icon: BarChart2 },
  ]

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">College Basketball</h1>
          <p className="text-sm text-gray-500 mt-1">
            Sharp money detection &amp; edge calculator for NCAAB lines
          </p>
        </div>
        <button
          onClick={() => {
            summaryQuery.refetch()
            bestBetsQuery.refetch()
            sharpQuery.refetch()
            edgeQuery.refetch()
          }}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Active Games"
          value={isLoading ? '–' : summary?.active_games ?? 0}
          icon={Activity}
          accent="bg-primary-500"
        />
        <StatCard
          label="+EV Bets Found"
          value={isLoading ? '–' : summary?.positive_ev_bets ?? 0}
          icon={DollarSign}
          accent="bg-green-500"
        />
        <StatCard
          label="Sharp Signals"
          value={isLoading ? '–' : summary?.sharp_signal_count ?? 0}
          icon={AlertTriangle}
          accent="bg-orange-500"
        />
        <StatCard
          label="Book Divergences"
          value={isLoading ? '–' : summary?.book_divergence_count ?? 0}
          icon={BarChart2}
          accent="bg-purple-500"
        />
      </div>

      {/* Top games quick view */}
      {summary?.top_games_by_edge && summary.top_games_by_edge.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Top Games by Edge</h2>
          <div className="space-y-2">
            {summary.top_games_by_edge.map((g, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                <span className="text-sm text-gray-800 font-medium">{g.game}</span>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-500">{g.sharp_books} sharp books</span>
                  <span className={clsx('text-sm font-bold', edgeColor(g.best_edge))}>
                    {formatPct(g.best_edge)} edge
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4 bg-white border border-gray-200 rounded-xl px-5 py-4">
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-600 font-medium">Min Edge:</label>
          <select
            value={minEdge}
            onChange={(e) => setMinEdge(Number(e.target.value))}
            className="text-sm border border-gray-300 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value={0.01}>1%</option>
            <option value={0.02}>2%</option>
            <option value={0.03}>3%</option>
            <option value={0.05}>5%</option>
            <option value={0.08}>8%</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-600 font-medium">Min Sharp Score:</label>
          <select
            value={minSharpScore}
            onChange={(e) => setMinSharpScore(Number(e.target.value))}
            className="text-sm border border-gray-300 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value={0}>Any</option>
            <option value={1}>Weak (1+)</option>
            <option value={2}>Moderate (2+)</option>
            <option value={3}>Strong (3+)</option>
          </select>
        </div>
        <div className="ml-auto flex items-center gap-1.5 text-xs text-gray-400">
          <Info className="w-3.5 h-3.5" />
          Auto-refreshes every 60s
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 rounded-xl p-1 w-fit">
        {tabs.map((tab) => {
          const Icon = tab.icon
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={clsx(
                'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                activeTab === tab.id
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              )}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Best Bets tab */}
      {activeTab === 'best-bets' && (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-gray-900">Best NCAAB Bets</h2>
              <p className="text-xs text-gray-500 mt-0.5">
                Ranked by composite score: edge × (1 + 0.25 × sharp score)
              </p>
            </div>
            {bestBetsQuery.data && (
              <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded-full font-medium">
                {bestBetsQuery.data.total_best_bets} bets
              </span>
            )}
          </div>

          {bestBetsQuery.isLoading ? (
            <div className="p-10 text-center text-gray-400 text-sm">Loading bets...</div>
          ) : !bestBetsQuery.data?.bets?.length ? (
            <div className="p-10 text-center text-gray-400 text-sm">
              No bets found matching current filters.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50">
                    <th className="py-3 pl-4 pr-3 text-xs font-medium text-gray-500">#</th>
                    <th className="py-3 px-3 text-xs font-medium text-gray-500">Game</th>
                    <th className="py-3 px-3 text-xs font-medium text-gray-500">Side / Book</th>
                    <th className="py-3 px-3 text-xs font-medium text-gray-500 text-center">Odds</th>
                    <th className="py-3 px-3 text-xs font-medium text-gray-500 text-center">Edge</th>
                    <th className="py-3 px-3 text-xs font-medium text-gray-500 text-center">EV/unit</th>
                    <th className="py-3 px-3 text-xs font-medium text-gray-500 text-center">Sharp</th>
                    <th className="py-3 px-3 text-xs font-medium text-gray-500 text-center">Kelly</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {bestBetsQuery.data.bets.map((bet, i) => (
                    <BestBetRow key={`${bet.game_id}-${bet.market}-${bet.side}`} bet={bet} rank={i + 1} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Sharp Signals tab */}
      {activeTab === 'sharp-signals' && (
        <div className="space-y-4">
          {/* Legend */}
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-800">
            <p className="font-semibold mb-1">Sharp Signal Types</p>
            <ul className="space-y-1 text-xs">
              <li><strong>Book Divergence</strong> – Sharp books (Pinnacle) give a meaningfully different probability than square books (FanDuel, DraftKings)</li>
              <li><strong>Line Movement</strong> – The line has moved from its opening price in a notable direction</li>
              <li><strong>RLM (Reverse Line Movement)</strong> – Public % heavily favors one side but the line moves the other way = sharp action on opposite side</li>
              <li><strong>Spread Discrepancy</strong> – Sharp and square books show different spread numbers (0.5+ point gap)</li>
            </ul>
          </div>

          {sharpQuery.isLoading ? (
            <div className="p-10 text-center text-gray-400 text-sm">Loading signals...</div>
          ) : !sharpQuery.data?.signals?.length ? (
            <div className="p-10 text-center text-gray-400 text-sm bg-white border border-gray-200 rounded-xl">
              No sharp signals detected with current filters.
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {sharpQuery.data.signals.map((sig, i) => (
                <SharpSignalCard key={`${sig.game_id}-${sig.market}-${i}`} signal={sig} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Edge Calculator tab */}
      {activeTab === 'edge' && (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-900">Edge Calculator</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Multiplicative devig across sharp books → true probability → vs best available price
            </p>
          </div>

          {edgeQuery.isLoading ? (
            <div className="p-10 text-center text-gray-400 text-sm">Computing edges...</div>
          ) : !edgeQuery.data?.bets?.length ? (
            <div className="p-10 text-center text-gray-400 text-sm">
              No positive-EV bets found at the current minimum edge filter.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50">
                    <th className="py-3 pl-4 pr-3 text-xs font-medium text-gray-500">Game</th>
                    <th className="py-3 px-3 text-xs font-medium text-gray-500">Market</th>
                    <th className="py-3 px-3 text-xs font-medium text-gray-500">Side</th>
                    <th className="py-3 px-3 text-xs font-medium text-gray-500 text-center">True Prob</th>
                    <th className="py-3 px-3 text-xs font-medium text-gray-500 text-center">Fair Odds</th>
                    <th className="py-3 px-3 text-xs font-medium text-gray-500 text-center">Mkt Implied</th>
                    <th className="py-3 px-3 text-xs font-medium text-gray-500 text-center">Edge</th>
                    <th className="py-3 px-3 text-xs font-medium text-gray-500 text-center">Best Price</th>
                    <th className="py-3 px-3 text-xs font-medium text-gray-500 text-center">Book</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {edgeQuery.data.bets.map((bet, i) => (
                    <tr key={i} className="hover:bg-gray-50">
                      <td className="py-3 pl-4 pr-3 text-sm font-medium text-gray-900">
                        {bet.away_team} @ {bet.home_team}
                      </td>
                      <td className="py-3 px-3 text-xs text-gray-500 capitalize">{bet.market}</td>
                      <td className="py-3 px-3 text-sm text-gray-800 font-medium">{bet.side}</td>
                      <td className="py-3 px-3 text-sm text-center font-semibold text-gray-900">
                        {formatPct(bet.true_prob)}
                      </td>
                      <td className="py-3 px-3 text-sm text-center text-gray-700">
                        {formatOdds(bet.fair_odds)}
                      </td>
                      <td className="py-3 px-3 text-sm text-center text-gray-500">
                        {formatPct(bet.market_implied_prob ?? 0)}
                      </td>
                      <td className="py-3 px-3 text-center">
                        <span className={clsx('text-sm font-bold', edgeColor(bet.edge))}>
                          {formatPct(bet.edge)}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-sm text-center font-bold text-gray-900">
                        {formatOdds(bet.best_available_odds)}
                      </td>
                      <td className="py-3 px-3 text-xs text-center text-gray-500 capitalize">
                        {bet.best_book}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
