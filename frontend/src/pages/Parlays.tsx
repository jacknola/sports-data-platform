import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/utils/api';
import type { Parlay, ParlayInsights, ParlayStats } from '@/types/api';

const SPORTS = ['NBA', 'NCAAB', 'NFL', 'NCAAF', 'MLB', 'NHL'];
const STATUSES = ['pending', 'won', 'lost', 'partial'];
const STAT_TYPES = ['PTS', 'REB', 'AST', '3PM', 'STL', 'BLK', 'PRA', 'TRB'];
type LegMarket = 'moneyline' | 'spread' | 'total' | 'player_prop';

interface LegDraft {
  market: LegMarket;
  game: string;
  team: string;
  opponent: string;
  player_name: string;
  stat_type: string;
  side: 'OVER' | 'UNDER';
  line: string;
  odds: string;
  reasoning: string;
}

interface ParlayDraft {
  title: string;
  sport: string;
  confidence_level: 'LOW' | 'MEDIUM' | 'HIGH';
  analysis: string;
  legs: LegDraft[];
}

const emptyLeg = (): LegDraft => ({
  market: 'player_prop', game: '', team: '', opponent: '',
  player_name: '', stat_type: 'PTS', side: 'OVER',
  line: '', odds: '', reasoning: '',
});

function buildPickText(leg: LegDraft): string {
  if (leg.market === 'player_prop')
    return `${leg.player_name} ${leg.side} ${leg.line} ${leg.stat_type}`.trim();
  if (leg.market === 'total') return `${leg.side} ${leg.line}`.trim();
  if (leg.market === 'spread')
    return `${leg.team} ${parseFloat(leg.line) > 0 ? '+' : ''}${leg.line}`;
  return `${leg.team} ML`;
}

function legToApiShape(leg: LegDraft) {
  return {
    market: leg.market,
    game: leg.game,
    team: leg.team,
    opponent: leg.opponent,
    pick: buildPickText(leg),
    line: leg.line !== '' ? parseFloat(leg.line) : null,
    odds: parseFloat(leg.odds) || -110,
    reasoning: leg.reasoning,
    confidence: 0.7,
  };
}

export default function Parlays() {
  const queryClient = useQueryClient();
  const [selectedSport, setSelectedSport] = useState<string>('');
  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedParlay, setSelectedParlay] = useState<Parlay | null>(null);
  const [isBuilding, setIsBuilding] = useState(false);
  const [draft, setDraft] = useState<ParlayDraft>({
    title: '', sport: 'NBA', confidence_level: 'MEDIUM', analysis: '', legs: [],
  });
  const [legDraft, setLegDraft] = useState<LegDraft>(emptyLeg());

  // Fetch parlays list
  const { data: parlays, isLoading: parlaysLoading } = useQuery<Parlay[]>({
    queryKey: ['parlays', selectedSport, selectedStatus],
    queryFn: () => api.get('/api/v1/parlays', { params: { sport: selectedSport || undefined, status: selectedStatus || undefined } }),
  });
  // Fetch performance stats
  const { data: stats } = useQuery<ParlayStats>({
    queryKey: ['parlays', 'stats'],
    queryFn: () => api.get('/api/v1/parlays/stats/performance'),
  });

  // Search mutation
  const searchMutation = useMutation<Parlay[], Error, string>({
    mutationFn: (query) => api.post('/api/v1/parlays/search', { query }),
    onSuccess: (results, query) => {
      queryClient.setQueryData(['parlays', 'search', query], results);
    },
  });

  // Update result mutation
  const updateMutation = useMutation({
    mutationFn: ({ parlayId, data }: { parlayId: string; data: { status: string; result?: Record<string, unknown>; actual_return?: number } }) =>
      api.post(`/api/v1/parlays/${parlayId}/update`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['parlays'] });
      queryClient.invalidateQueries({ queryKey: ['parlays', 'stats'] });
    },
  });

  // Twitter post mutation
  const tweetMutation = useMutation({
    mutationFn: ({ parlayId, asThread }: { parlayId: string; asThread: boolean }) =>
      api.post(`/api/v1/parlays/${parlayId}/post-twitter`, { as_thread: asThread }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['parlays'] });
    },
  });

  // Create parlay mutation
  const createMutation = useMutation({
    mutationFn: (data: object) => api.post('/api/v1/parlays', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['parlays'] });
      setIsBuilding(false);
      setDraft({ title: '', sport: 'NBA', confidence_level: 'MEDIUM', analysis: '', legs: [] });
      setLegDraft(emptyLeg());
    },
  });

  // Fetch insights for selected parlay
  const { data: insights } = useQuery<ParlayInsights>({
    queryKey: ['parlays', selectedParlay?.parlay_id, 'insights'],
    queryFn: () => api.get(`/api/v1/parlays/${selectedParlay?.parlay_id}/insights`),
    enabled: !!selectedParlay,
  });
  // Handle search
  const handleSearch = () => {
    if (searchQuery.trim()) {
      searchMutation.mutate(searchQuery);
    }
  };

  const getConfidenceColor = (level?: string) => {
    switch (level) {
      case 'HIGH': return 'text-green-400';
      case 'MEDIUM': return 'text-yellow-400';
      case 'LOW': return 'text-orange-400';
      case 'MAX': return 'text-purple-400';
      default: return 'text-gray-400';
    }
  };

  const getStatusColor = (status?: string) => {
    switch (status) {
      case 'won': return 'bg-green-600';
      case 'lost': return 'bg-red-600';
      case 'pending': return 'bg-blue-600';
      case 'partial': return 'bg-yellow-600';
      default: return 'bg-gray-600';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Parlay RAG Dashboard</h1>
        <div className="flex items-center gap-4">
          {stats && (
            <span className="text-sm text-gray-400">
              Win Rate: <span className={stats.win_rate > 50 ? 'text-green-400' : 'text-red-400'}>{stats.win_rate.toFixed(1)}%</span>
            </span>
          )}
          <button
            onClick={() => { setIsBuilding(!isBuilding); setSelectedParlay(null); }}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${isBuilding ? 'bg-gray-600 text-white' : 'bg-accent-500 text-white hover:bg-accent-600'}`}
          >
            {isBuilding ? '✕ Cancel' : '+ Build Parlay'}
          </button>
        </div>
      </div>

      {/* Performance Stats */}
      {stats && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
          <div className="rounded-lg bg-gray-800 p-4">
            <div className="text-sm text-gray-400">Total</div>
            <div className="text-2xl font-bold text-white">{stats.total_parlays}</div>
          </div>
          <div className="rounded-lg bg-gray-800 p-4">
            <div className="text-sm text-gray-400">Pending</div>
            <div className="text-2xl font-bold text-blue-400">{stats.pending || 0}</div>
          </div>
          <div className="rounded-lg bg-gray-800 p-4">
            <div className="text-sm text-gray-400">Won</div>
            <div className="text-2xl font-bold text-green-400">{stats.won}</div>
          </div>
          <div className="rounded-lg bg-gray-800 p-4">
            <div className="text-sm text-gray-400">Lost</div>
            <div className="text-2xl font-bold text-red-400">{stats.lost}</div>
          </div>
          <div className="rounded-lg bg-gray-800 p-4">
            <div className="text-sm text-gray-400">ROI</div>
            <div className={`text-2xl font-bold ${stats.overall_roi > 0 ? 'text-green-400' : 'text-red-400'}`}>
              {stats.overall_roi > 0 ? '+' : ''}{stats.overall_roi.toFixed(1)}%
            </div>
          </div>
        </div>
      )}

      {/* Search & Filters */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Search parlays..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="rounded-lg bg-gray-800 px-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <button
            onClick={handleSearch}
            className="rounded-lg bg-primary-600 px-4 py-2 text-white hover:bg-primary-700"
          >
            Search
          </button>
        </div>
        <select
          value={selectedSport}
          onChange={(e) => setSelectedSport(e.target.value)}
          className="rounded-lg bg-gray-800 px-4 py-2 text-white"
        >
          <option value="">All Sports</option>
          {SPORTS.map((sport) => (
            <option key={sport} value={sport}>{sport}</option>
          ))}
        </select>
        <select
          value={selectedStatus}
          onChange={(e) => setSelectedStatus(e.target.value)}
          className="rounded-lg bg-gray-800 px-4 py-2 text-white"
        >
          <option value="">All Statuses</option>
          {STATUSES.map((status) => (
            <option key={status} value={status}>{status.charAt(0).toUpperCase() + status.slice(1)}</option>
          ))}
        </select>
      </div>
      {/* Parlay Builder */}
      {isBuilding && (
        <div className="rounded-lg bg-gray-800 p-6 space-y-5">
          <h2 className="text-lg font-semibold text-white">Build New Parlay</h2>

          {/* Parlay metadata */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs text-gray-400">Title</label>
              <input
                type="text"
                placeholder="e.g. NBA Tuesday Parlay"
                value={draft.title}
                onChange={(e) => setDraft({ ...draft, title: e.target.value })}
                className="w-full rounded bg-gray-700 px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-accent-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-gray-400">Sport</label>
              <select
                value={draft.sport}
                onChange={(e) => setDraft({ ...draft, sport: e.target.value })}
                className="w-full rounded bg-gray-700 px-3 py-2 text-sm text-white focus:outline-none"
              >
                {SPORTS.map((s) => <option key={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-gray-400">Confidence</label>
              <select
                value={draft.confidence_level}
                onChange={(e) => setDraft({ ...draft, confidence_level: e.target.value as ParlayDraft['confidence_level'] })}
                className="w-full rounded bg-gray-700 px-3 py-2 text-sm text-white focus:outline-none"
              >
                {['LOW', 'MEDIUM', 'HIGH'].map((c) => <option key={c}>{c}</option>)}
              </select>
            </div>
          </div>

          {/* Current legs */}
          {draft.legs.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-medium text-gray-300">Legs ({draft.legs.length})</h3>
              <div className="space-y-2">
                {draft.legs.map((leg, i) => (
                  <div key={i} className="flex items-center justify-between rounded bg-gray-700 px-3 py-2 text-sm">
                    <div>
                      <span className="rounded bg-gray-600 px-1.5 py-0.5 text-xs text-gray-300 mr-2">{leg.market}</span>
                      <span className="text-white font-medium">{buildPickText(leg)}</span>
                      {leg.game && <span className="ml-2 text-gray-400 text-xs">{leg.game}</span>}
                      <span className="ml-2 text-yellow-400">{parseFloat(leg.odds) > 0 ? '+' : ''}{leg.odds}</span>
                    </div>
                    <button
                      onClick={() => setDraft({ ...draft, legs: draft.legs.filter((_, idx) => idx !== i) })}
                      className="ml-3 text-red-400 hover:text-red-300 text-xs"
                    >✕</button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Add Leg form */}
          <div className="rounded border border-gray-600 p-4 space-y-3">
            <h3 className="text-sm font-medium text-gray-300">Add Leg</h3>

            {/* Market type selector */}
            <div className="flex gap-2 flex-wrap">
              {(['player_prop', 'moneyline', 'spread', 'total'] as LegMarket[]).map((m) => (
                <button
                  key={m}
                  onClick={() => setLegDraft({ ...emptyLeg(), market: m })}
                  className={`rounded px-3 py-1.5 text-xs font-medium transition-colors ${
                    legDraft.market === m ? 'bg-accent-500 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                >
                  {m === 'player_prop' ? '🏀 Player Prop' : m === 'moneyline' ? 'Moneyline' : m === 'spread' ? 'Spread' : 'Total'}
                </button>
              ))}
            </div>

            <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
              {/* Player Prop specific fields */}
              {legDraft.market === 'player_prop' && (
                <>
                  <div className="md:col-span-1">
                    <label className="mb-1 block text-xs text-gray-400">Player Name</label>
                    <input
                      type="text"
                      placeholder="e.g. LeBron James"
                      value={legDraft.player_name}
                      onChange={(e) => setLegDraft({ ...legDraft, player_name: e.target.value })}
                      className="w-full rounded bg-gray-700 px-2 py-1.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-accent-500"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-gray-400">Stat</label>
                    <select
                      value={legDraft.stat_type}
                      onChange={(e) => setLegDraft({ ...legDraft, stat_type: e.target.value })}
                      className="w-full rounded bg-gray-700 px-2 py-1.5 text-sm text-white focus:outline-none"
                    >
                      {STAT_TYPES.map((s) => <option key={s}>{s}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-gray-400">Side</label>
                    <div className="flex rounded overflow-hidden">
                      {(['OVER', 'UNDER'] as const).map((s) => (
                        <button
                          key={s}
                          onClick={() => setLegDraft({ ...legDraft, side: s })}
                          className={`flex-1 py-1.5 text-xs font-medium transition-colors ${
                            legDraft.side === s ? (s === 'OVER' ? 'bg-green-600 text-white' : 'bg-red-600 text-white') : 'bg-gray-700 text-gray-300'
                          }`}
                        >{s}</button>
                      ))}
                    </div>
                  </div>
                </>
              )}

              {/* Moneyline / Spread team selector */}
              {(legDraft.market === 'moneyline' || legDraft.market === 'spread') && (
                <div>
                  <label className="mb-1 block text-xs text-gray-400">Team</label>
                  <input
                    type="text"
                    placeholder="e.g. Lakers"
                    value={legDraft.team}
                    onChange={(e) => setLegDraft({ ...legDraft, team: e.target.value })}
                    className="w-full rounded bg-gray-700 px-2 py-1.5 text-sm text-white placeholder-gray-500 focus:outline-none"
                  />
                </div>
              )}

              {/* Total side selector */}
              {legDraft.market === 'total' && (
                <div>
                  <label className="mb-1 block text-xs text-gray-400">Side</label>
                  <div className="flex rounded overflow-hidden">
                    {(['OVER', 'UNDER'] as const).map((s) => (
                      <button
                        key={s}
                        onClick={() => setLegDraft({ ...legDraft, side: s })}
                        className={`flex-1 py-1.5 text-xs font-medium ${legDraft.side === s ? 'bg-accent-500 text-white' : 'bg-gray-700 text-gray-300'}`}
                      >{s}</button>
                    ))}
                  </div>
                </div>
              )}

              {/* Line (prop line / spread / total) */}
              {legDraft.market !== 'moneyline' && (
                <div>
                  <label className="mb-1 block text-xs text-gray-400">
                    {legDraft.market === 'player_prop' ? 'Prop Line' : legDraft.market === 'total' ? 'Total' : 'Spread'}
                  </label>
                  <input
                    type="number"
                    step="0.5"
                    placeholder="e.g. 24.5"
                    value={legDraft.line}
                    onChange={(e) => setLegDraft({ ...legDraft, line: e.target.value })}
                    className="w-full rounded bg-gray-700 px-2 py-1.5 text-sm text-white placeholder-gray-500 focus:outline-none"
                  />
                </div>
              )}

              {/* Odds */}
              <div>
                <label className="mb-1 block text-xs text-gray-400">Odds (American)</label>
                <input
                  type="number"
                  placeholder="-110"
                  value={legDraft.odds}
                  onChange={(e) => setLegDraft({ ...legDraft, odds: e.target.value })}
                  className="w-full rounded bg-gray-700 px-2 py-1.5 text-sm text-white placeholder-gray-500 focus:outline-none"
                />
              </div>

              {/* Game/Matchup */}
              <div className="md:col-span-2">
                <label className="mb-1 block text-xs text-gray-400">
                  {legDraft.market === 'player_prop' ? "Team / Matchup (optional)" : "Matchup"}
                </label>
                <input
                  type="text"
                  placeholder={legDraft.market === 'player_prop' ? "e.g. Lakers vs Warriors" : "e.g. Lakers @ Warriors"}
                  value={legDraft.game}
                  onChange={(e) => setLegDraft({ ...legDraft, game: e.target.value })}
                  className="w-full rounded bg-gray-700 px-2 py-1.5 text-sm text-white placeholder-gray-500 focus:outline-none"
                />
              </div>
            </div>

            {/* Reasoning */}
            <div>
              <label className="mb-1 block text-xs text-gray-400">Reasoning (optional)</label>
              <input
                type="text"
                placeholder="Why this leg..."
                value={legDraft.reasoning}
                onChange={(e) => setLegDraft({ ...legDraft, reasoning: e.target.value })}
                className="w-full rounded bg-gray-700 px-2 py-1.5 text-sm text-white placeholder-gray-500 focus:outline-none"
              />
            </div>

            {/* Preview + Add button */}
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-400 italic">
                Preview: <span className="text-white">{buildPickText(legDraft) || '—'}</span>
                {legDraft.odds && <span className="ml-1 text-yellow-400">{parseFloat(legDraft.odds) > 0 ? '+' : ''}{legDraft.odds}</span>}
              </span>
              <button
                onClick={() => {
                  if (!buildPickText(legDraft).trim()) return;
                  setDraft({ ...draft, legs: [...draft.legs, { ...legDraft }] });
                  setLegDraft(emptyLeg());
                }}
                className="rounded bg-green-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-green-500 transition-colors"
              >+ Add Leg</button>
            </div>
          </div>

          {/* Analysis textarea */}
          <div>
            <label className="mb-1 block text-xs text-gray-400">Analysis / Notes</label>
            <textarea
              rows={2}
              placeholder="Overall reasoning for this parlay..."
              value={draft.analysis}
              onChange={(e) => setDraft({ ...draft, analysis: e.target.value })}
              className="w-full rounded bg-gray-700 px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-accent-500"
            />
          </div>

          {/* Submit */}
          <div className="flex items-center gap-3">
            <button
              disabled={draft.legs.length < 2 || !draft.title || createMutation.isPending}
              onClick={() => {
                createMutation.mutate({
                  title: draft.title,
                  sport: draft.sport,
                  confidence_level: draft.confidence_level,
                  confidence_score: draft.confidence_level === 'HIGH' ? 0.8 : draft.confidence_level === 'MEDIUM' ? 0.65 : 0.5,
                  analysis: draft.analysis,
                  legs: draft.legs.map(legToApiShape),
                });
              }}
              className="rounded-lg bg-accent-500 px-6 py-2 text-sm font-semibold text-white hover:bg-accent-600 disabled:opacity-40 transition-colors"
            >
              {createMutation.isPending ? 'Creating…' : `Create Parlay (${draft.legs.length} leg${draft.legs.length !== 1 ? 's' : ''})`}
            </button>
            {draft.legs.length < 2 && (
              <span className="text-xs text-gray-500">Need at least 2 legs</span>
            )}
            {createMutation.isError && (
              <span className="text-xs text-red-400">Failed to create parlay</span>
            )}
          </div>
        </div>
      )}

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Parlay List */}
        <div className="lg:col-span-2">
          <div className="rounded-lg bg-gray-800 p-4">
            <h2 className="mb-4 text-lg font-semibold text-white">Parlays</h2>
            {parlaysLoading ? (
              <div className="py-8 text-center text-gray-500">Loading...</div>
            ) : parlays && parlays.length > 0 ? (
              <div className="space-y-3">
                {parlays.map((parlay) => (
                  <div
                    key={parlay.parlay_id}
                    onClick={() => setSelectedParlay(parlay)}
                    className={`cursor-pointer rounded-lg p-4 transition-colors ${
                      selectedParlay?.parlay_id === parlay.parlay_id
                        ? 'bg-primary-600'
                        : 'bg-gray-700 hover:bg-gray-600'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className={`rounded-full px-2 py-0.5 text-xs ${getStatusColor(parlay.status)}`}>
                            {parlay.status || 'pending'}
                          </span>
                          <span className="text-sm text-gray-400">{parlay.sport}</span>
                        </div>
                        <div className="mt-1 font-medium text-white">{parlay.title || `Parlay ${parlay.parlay_id.slice(0, 8)}`}</div>
                        {parlay.legs && (
                          <div className="mt-1 text-sm text-gray-400">
                            {parlay.legs.length} {parlay.legs.length === 1 ? 'leg' : 'legs'} • Total odds: {parlay.total_odds}
                          </div>
                        )}
                      </div>
                      <div className="text-right">
                        <div className={`text-sm font-semibold ${getConfidenceColor(parlay.confidence_level)}`}>
                          {parlay.confidence_level || 'N/A'}
                        </div>
                        {parlay.confidence_score && (
                          <div className="text-xs text-gray-400">{parlay.confidence_score.toFixed(0)}%</div>
                        )}
                        {parlay.roi !== undefined && (
                          <div className={`mt-1 text-xs ${parlay.roi > 0 ? 'text-green-400' : 'text-red-400'}`}>
                            ROI: {parlay.roi > 0 ? '+' : ''}{parlay.roi.toFixed(1)}%
                          </div>
                        )}
                      </div>
                    </div>
                    {parlay.twitter_post_id && (
                      <div className="mt-2 text-xs text-blue-400">Posted to Twitter</div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-8 text-center text-gray-500">No parlays found</div>
            )}
          </div>
        </div>
        {/* Selected Parlay Details */}
        <div className="space-y-4">
          {selectedParlay ? (
            <>
              {/* Parlay Details */}
              <div className="rounded-lg bg-gray-800 p-4">
                <h2 className="mb-4 text-lg font-semibold text-white">
                  {selectedParlay.title || `Parlay ${selectedParlay.parlay_id.slice(0, 8)}`}
                </h2>
                
                <div className="space-y-3">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Sport:</span>
                    <span className="text-white">{selectedParlay.sport}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Confidence:</span>
                    <span className={`${getConfidenceColor(selectedParlay.confidence_level)}`}>
                      {selectedParlay.confidence_level} {selectedParlay.confidence_score && `(${selectedParlay.confidence_score.toFixed(0)}%)`}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Total Odds:</span>
                    <span className="text-white">{selectedParlay.total_odds}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Payout:</span>
                    <span className="text-white">{selectedParlay.potential_payout_multiplier}x</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Suggested Units:</span>
                    <span className="text-white">{selectedParlay.suggested_unit_size}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Status:</span>
                    <span className={`rounded-full px-2 py-0.5 text-xs ${getStatusColor(selectedParlay.status)}`}>
                      {selectedParlay.status}
                    </span>
                  </div>

                  {selectedParlay.analysis && (
                    <div className="mt-3">
                      <div className="text-sm text-gray-400">Analysis:</div>
                      <div className="mt-1 text-sm text-white">{selectedParlay.analysis}</div>
                    </div>
                  )}
                </div>

                {/* Legs */}
                {selectedParlay.legs && selectedParlay.legs.length > 0 && (
                  <div className="mt-4">
                    <div className="text-sm font-medium text-gray-300">Legs</div>
                    <div className="mt-2 space-y-2">
                      {selectedParlay.legs.map((leg, idx) => (
                        <div key={idx} className="rounded bg-gray-700 p-2 text-sm">
                          <div className="font-medium text-white">{leg.pick}</div>
                          <div className="text-gray-400">
                            {leg.team} vs {leg.opponent} • {leg.market} {leg.line}
                          </div>
                          <div className="text-gray-500">{leg.reasoning}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Risk Factors */}
                {selectedParlay.risks && selectedParlay.risks.length > 0 && (
                  <div className="mt-4">
                    <div className="text-sm font-medium text-gray-300">Risk Factors</div>
                    <div className="mt-1 space-y-1">
                      {selectedParlay.risks.map((risk, idx) => (
                        <div key={idx} className="text-sm text-red-400">⚠️ {risk}</div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="mt-4 space-y-2">
                  {selectedParlay.status === 'pending' && (
                    <div className="flex gap-2">
                      <button
                        onClick={() => updateMutation.mutate({
                          parlayId: selectedParlay.parlay_id,
                          data: { status: 'won' },
                        })}
                        className="flex-1 rounded-lg bg-green-600 px-3 py-2 text-sm text-white hover:bg-green-700"
                      >
                        Mark Won
                      </button>
                      <button
                        onClick={() => updateMutation.mutate({
                          parlayId: selectedParlay.parlay_id,
                          data: { status: 'lost' },
                        })}
                        className="flex-1 rounded-lg bg-red-600 px-3 py-2 text-sm text-white hover:bg-red-700"
                      >
                        Mark Lost
                      </button>
                    </div>
                  )}
                  {!selectedParlay.twitter_post_id && selectedParlay.status === 'pending' && (
                    <button
                      onClick={() => tweetMutation.mutate({ parlayId: selectedParlay.parlay_id, asThread: !!(selectedParlay.legs && selectedParlay.legs.length > 3) })}
                      className="w-full rounded-lg bg-blue-600 px-3 py-2 text-sm text-white hover:bg-blue-700"
                    >
                      Post to Twitter
                    </button>
                  )}
                </div>
              </div>
              {/* RAG Insights */}
              {insights && (
                <div className="rounded-lg bg-gray-800 p-4">
                  <h2 className="mb-4 text-lg font-semibold text-white">RAG Insights</h2>
                  
                  <div className="space-y-3">
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Similar Parlays:</span>
                      <span className="text-white">{insights.similar_parlays_found}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Historical Win Rate:</span>
                      <span className={insights.historical_win_rate > 0.5 ? 'text-green-400' : 'text-red-400'}>
                        {(insights.historical_win_rate * 100).toFixed(1)}%
                      </span>
                    </div>

                    {insights.recommendation && (
                      <div className="mt-2">
                        <div className="text-sm text-gray-400">Recommendation:</div>
                        <div className="mt-1 text-sm text-white">{insights.recommendation}</div>
                      </div>
                    )}
                    
                    {insights.similar_parlays && insights.similar_parlays.length > 0 && (
                      <div className="mt-3">
                        <div className="text-sm font-medium text-gray-300">Similar Parlays</div>
                        <div className="mt-1 space-y-1">
                          {insights.similar_parlays.slice(0, 5).map((p, idx) => (
                            <div key={idx} className="text-xs text-gray-400">
                              {p.title || p.id.slice(0, 8)} — {(p.similarity * 100).toFixed(0)}% match
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="rounded-lg bg-gray-800 p-4">
              <div className="py-8 text-center text-gray-500">
                Select a parlay to view details
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
