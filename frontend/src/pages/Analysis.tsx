import { useState } from 'react'
import api from '@/utils/api'

type PredictionResponse = {
  player: string
  market: string
  line: number
  probabilities: { over: number; under: number }
  fair_odds: {
    over_american: number
    under_american: number
    over_decimal: number
    under_decimal: number
  }
  offered_odds: {
    over_american: number
    under_american: number
  }
  expected_value: { over: number; under: number }
  kelly_fraction: { over: number; under: number }
  recommendation: { side: string; stake_fraction: number; best_ev: number }
}

export default function Analysis() {
  const [player, setPlayer] = useState('')
  const [market, setMarket] = useState('points')
  const [line, setLine] = useState<number>(24.5)
  const [history, setHistory] = useState('30, 26, 18, 35, 22')
  const [overOdds, setOverOdds] = useState('-110')
  const [underOdds, setUnderOdds] = useState('-110')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<PredictionResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const parseHistory = (input: string) =>
    input
      .split(',')
      .map((x) => x.trim())
      .filter((x) => x.length > 0)
      .map((x) => Number(x))
      .filter((x) => !Number.isNaN(x))

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const payload = {
        player,
        market,
        line: Number(line),
        history: parseHistory(history),
        side_odds: { over: Number(overOdds), under: Number(underOdds) },
      }
      const { data } = await api.post<PredictionResponse>('/api/v1/player-props/predict', payload)
      setResult(data)
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to get prediction')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Analysis</h1>
        <p className="text-gray-600">Player prop over/under predictor</p>
      </div>

      <form onSubmit={onSubmit} className="card space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="label">Player</label>
            <input className="input" value={player} onChange={(e) => setPlayer(e.target.value)} placeholder="Player name" />
          </div>
          <div>
            <label className="label">Market</label>
            <select className="input" value={market} onChange={(e) => setMarket(e.target.value)}>
              <option value="points">Points</option>
              <option value="assists">Assists</option>
              <option value="rebounds">Rebounds</option>
              <option value="pra">PRA</option>
              <option value="threes">3PM</option>
            </select>
          </div>
          <div>
            <label className="label">Line</label>
            <input className="input" type="number" step="0.5" value={line} onChange={(e) => setLine(Number(e.target.value))} />
          </div>
        </div>

        <div>
          <label className="label">Recent game stats (comma separated, most recent first)</label>
          <input className="input" value={history} onChange={(e) => setHistory(e.target.value)} placeholder="e.g. 30, 26, 18, 35, 22" />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="label">Over odds (American)</label>
            <input className="input" value={overOdds} onChange={(e) => setOverOdds(e.target.value)} />
          </div>
          <div>
            <label className="label">Under odds (American)</label>
            <input className="input" value={underOdds} onChange={(e) => setUnderOdds(e.target.value)} />
          </div>
        </div>

        <div className="flex gap-3">
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Predicting…' : 'Predict'}
          </button>
          {error && <div className="text-red-600 text-sm self-center">{error}</div>}
        </div>
      </form>

      {result && (
        <div className="card">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-xl font-bold text-gray-900">
                {result.player} – {result.market} {result.line}
              </h3>
              <p className="text-gray-600">Model: {result.recommendation.side.toUpperCase()} · Stake: {(result.recommendation.stake_fraction * 100).toFixed(2)}%</p>
            </div>
            <div className="text-right">
              <div className="text-2xl font-bold">
                EV: {(Math.max(result.expected_value.over, result.expected_value.under) * 100).toFixed(1)}%
              </div>
              <div className="text-sm text-gray-500">Kelly (O/U): {(result.kelly_fraction.over * 100).toFixed(1)}% / {(result.kelly_fraction.under * 100).toFixed(1)}%</div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-6">
            <div>
              <p className="text-xs text-gray-500 mb-1">Probabilities</p>
              <div className="text-lg font-semibold">Over {(result.probabilities.over * 100).toFixed(1)}% · Under {(result.probabilities.under * 100).toFixed(1)}%</div>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Fair Odds (American)</p>
              <div className="text-lg font-semibold">Over {result.fair_odds.over_american} · Under {result.fair_odds.under_american}</div>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Offered Odds</p>
              <div className="text-lg font-semibold">Over {result.offered_odds.over_american} · Under {result.offered_odds.under_american}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

