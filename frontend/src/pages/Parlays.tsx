import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/utils/api';
import type { Parlay, ParlayInsights, ParlayStats } from '@/types/api';

// Sport filter options
const SPORTS = ['NBA', 'NCAAB', 'NFL', 'NCAAF', 'MLB', 'NHL'];
const STATUSES = ['pending', 'won', 'lost', 'partial'];

export default function Parlays() {
  const queryClient = useQueryClient();
  const [selectedSport, setSelectedSport] = useState<string>('');
  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedParlay, setSelectedParlay] = useState<Parlay | null>(null);

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
        <div className="text-sm text-gray-400">
          {stats && (
            <span>
              Win Rate: <span className={stats.win_rate > 50 ? 'text-green-400' : 'text-red-400'}>{stats.win_rate.toFixed(1)}%</span>
            </span>
          )}
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
