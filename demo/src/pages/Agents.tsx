import { useEffect, useState } from 'react';
import { getDashboardAgents, AgentTrustScore } from '../api/client';

export default function Agents() {
  const [agents, setAgents] = useState<AgentTrustScore[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getDashboardAgents()
      .then(setAgents)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-gray-400 text-sm p-8">Loading agents…</div>;
  if (error) return <div className="text-red-400 text-sm p-8">Error: {error}</div>;

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold tracking-tight">Agent Trust Scores</h1>

      {agents.length === 0 ? (
        <div className="soc-card text-center text-gray-500 text-sm py-12">
          No agents registered yet.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-500 border-b border-pact-border">
                <th className="text-left py-2 pr-4 font-medium">Agent ID</th>
                <th className="text-left py-2 pr-4 font-medium">Owner</th>
                <th className="text-left py-2 pr-4 font-medium">Risk Tier</th>
                <th className="text-left py-2 pr-4 font-medium" style={{ minWidth: 160 }}>
                  Trust Score
                </th>
                <th className="text-right py-2 pr-4 font-medium">Runs</th>
                <th className="text-right py-2 pr-4 font-medium">Blocked</th>
                <th className="text-left py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((a) => (
                <tr
                  key={a.agent_id}
                  className="border-b border-pact-border/50 hover:bg-pact-surface/60 transition-colors"
                >
                  <td className="py-2.5 pr-4 font-mono text-pact-info">{a.agent_id}</td>
                  <td className="py-2.5 pr-4 text-gray-300">{a.owner}</td>
                  <td className="py-2.5 pr-4">
                    <span className={tierColor(a.risk_tier)}>{a.risk_tier}</span>
                  </td>
                  <td className="py-2.5 pr-4">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-2 bg-pact-bg rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all"
                          style={{
                            width: `${a.trust_score}%`,
                            background: trustColor(a.trust_score),
                          }}
                        />
                      </div>
                      <span
                        className="font-mono text-xs w-8 text-right"
                        style={{ color: trustColor(a.trust_score) }}
                      >
                        {a.trust_score}
                      </span>
                    </div>
                  </td>
                  <td className="py-2.5 pr-4 text-right font-mono text-gray-300">{a.total_runs}</td>
                  <td className="py-2.5 pr-4 text-right font-mono text-red-400">{a.blocked_actions}</td>
                  <td className="py-2.5">
                    <span
                      className={`badge ${
                        a.status === 'active' ? 'badge-allow' : 'badge-block'
                      }`}
                    >
                      {a.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function tierColor(tier: string): string {
  switch (tier) {
    case 'critical': return 'badge badge-block';
    case 'high': return 'badge bg-orange-500/20 text-orange-400 border border-orange-500/30';
    case 'medium': return 'badge bg-yellow-500/20 text-yellow-400 border border-yellow-500/30';
    default: return 'badge badge-allow';
  }
}

function trustColor(score: number): string {
  if (score >= 80) return '#22c55e';
  if (score >= 50) return '#f59e0b';
  return '#ef4444';
}
