import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getRuns, RunSummary } from '../api/client';

export default function Runs() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const fetchRuns = useCallback(() => {
    getRuns()
      .then((data) => {
        setRuns(data);
        setError('');
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchRuns();
    const id = window.setInterval(fetchRuns, 3000);
    return () => window.clearInterval(id);
  }, [fetchRuns]);

  if (loading) return <div className="text-gray-400 text-sm p-8">Loading runs…</div>;
  if (error) return <div className="text-red-400 text-sm p-8">Error: {error}</div>;

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold tracking-tight">Agent Runs</h1>

      {runs.length === 0 ? (
        <div className="soc-card text-center text-gray-500 text-sm py-12">
          No runs recorded yet. Execute a scenario to get started.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-500 border-b border-pact-border">
                <th className="text-left py-2 pr-4 font-medium">Run ID</th>
                <th className="text-left py-2 pr-4 font-medium">Scenario</th>
                <th className="text-left py-2 pr-4 font-medium">Agent</th>
                <th className="text-left py-2 pr-4 font-medium">Status</th>
                <th className="text-left py-2 pr-4 font-medium">Severity</th>
                <th className="text-right py-2 pr-4 font-medium">Allowed</th>
                <th className="text-right py-2 pr-4 font-medium">Blocked</th>
                <th className="text-right py-2 pr-4 font-medium">Risk</th>
                <th className="text-left py-2 font-medium">Ledger</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => {
                const severity = r.max_risk_score >= 90 ? 'critical'
                  : r.max_risk_score >= 60 ? 'high'
                  : r.max_risk_score >= 25 ? 'medium'
                  : 'low';

                return (
                  <tr
                    key={r.run_id}
                    className="border-b border-pact-border/50 hover:bg-pact-surface/60 cursor-pointer transition-colors"
                    onClick={() => navigate(`/runs/${r.run_id}`)}
                  >
                    <td className="py-2 pr-4 font-mono text-pact-info">{r.run_id.slice(0, 12)}…</td>
                    <td className="py-2 pr-4 font-mono text-gray-300">{r.scenario_name ?? '—'}</td>
                    <td className="py-2 pr-4 font-mono text-gray-400">{r.agent_id}</td>
                    <td className="py-2 pr-4">
                      <span
                        className={`badge ${
                          r.status === 'completed'
                            ? 'badge-allow'
                            : r.status === 'failed'
                            ? 'badge-block'
                            : 'badge-approval'
                        }`}
                      >
                        {r.status}
                      </span>
                    </td>
                    <td className="py-2 pr-4">
                      <span className={severityColor(severity)}>{severity}</span>
                    </td>
                    <td className="py-2 pr-4 text-right font-mono text-green-400">{r.allowed_actions}</td>
                    <td className="py-2 pr-4 text-right font-mono text-red-400">{r.blocked_actions}</td>
                    <td className="py-2 pr-4 text-right font-mono">{r.max_risk_score}</td>
                    <td className="py-2">
                      {r.ledger_valid === null || r.ledger_valid === undefined ? (
                        <span className="text-gray-500">not checked</span>
                      ) : r.ledger_valid ? (
                        <span className="text-green-400">✓ verified</span>
                      ) : (
                        <span className="text-red-400">✗ invalid</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function severityColor(s: string): string {
  switch (s) {
    case 'critical': return 'badge badge-block';
    case 'high': return 'badge bg-orange-500/20 text-orange-400 border border-orange-500/30';
    case 'medium': return 'badge bg-yellow-500/20 text-yellow-400 border border-yellow-500/30';
    default: return 'badge badge-allow';
  }
}
