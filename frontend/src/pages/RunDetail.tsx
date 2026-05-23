import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ChevronDown, ChevronRight, ExternalLink, Activity } from 'lucide-react';
import { getRun, RunDetail as RunDetailType, ActionData } from '../api/client';
import ActionGraph from '../components/ActionGraph';

export default function RunDetail() {
  const { runId } = useParams<{ runId: string }>();
  const [run, setRun] = useState<RunDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState<number | null>(null);
  const [showGraph, setShowGraph] = useState(false);

  useEffect(() => {
    if (!runId) return;
    getRun(runId)
      .then(setRun)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [runId]);

  if (loading) return <div className="text-gray-400 text-sm p-8">Loading run…</div>;
  if (error) return <div className="text-red-400 text-sm p-8">Error: {error}</div>;
  if (!run) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <Link to="/runs" className="text-xs text-pact-accent hover:underline mb-1 inline-block">
            ← Back to Runs
          </Link>
          <h1 className="text-lg font-semibold tracking-tight">
            Run <span className="font-mono text-pact-info">{run.run_id.slice(0, 16)}…</span>
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to={`/runs/${run.run_id}/replay`}
            className="flex items-center gap-1.5 text-xs bg-pact-accent/15 text-pact-accent px-3 py-1.5 rounded hover:bg-pact-accent/25 transition-colors"
          >
            <Activity className="w-3.5 h-3.5" />
            Replay
          </Link>
        </div>
      </div>

      {/* Info cards */}
      <div className="grid grid-cols-4 gap-4">
        <InfoCard label="Scenario" value={run.scenario_name ?? '—'} />
        <InfoCard label="Agent" value={run.agent_id} />
        <InfoCard label="Status" value={run.status} />
        <InfoCard label="Actions" value={`${run.actions.length} steps`} />
      </div>

      {run.user_goal && (
        <div className="soc-card">
          <div className="text-xs text-gray-500 mb-1">User Goal</div>
          <div className="text-sm text-gray-200">{run.user_goal}</div>
        </div>
      )}

      {/* Graph toggle */}
      <button
        onClick={() => setShowGraph(!showGraph)}
        className="text-xs text-pact-accent hover:underline flex items-center gap-1"
      >
        <ExternalLink className="w-3 h-3" />
        {showGraph ? 'Hide' : 'Show'} Action Graph
      </button>

      {showGraph && (
        <div className="soc-card" style={{ height: 420 }}>
          <ActionGraph run={run} />
        </div>
      )}

      {/* Actions table */}
      <div className="soc-card">
        <h2 className="text-sm font-medium mb-3 text-gray-300">Actions</h2>
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gray-500 border-b border-pact-border">
              <th className="text-left py-2 pr-3 font-medium w-8" />
              <th className="text-left py-2 pr-3 font-medium">Step</th>
              <th className="text-left py-2 pr-3 font-medium">Tool</th>
              <th className="text-left py-2 pr-3 font-medium">Status</th>
              <th className="text-right py-2 pr-3 font-medium">Risk</th>
              <th className="text-left py-2 font-medium">Provenance</th>
            </tr>
          </thead>
          <tbody>
            {run.actions.map((a) => (
              <ActionRow
                key={a.step_id}
                action={a}
                expanded={expanded === a.step_id}
                onToggle={() => setExpanded(expanded === a.step_id ? null : a.step_id)}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ActionRow({
  action: a,
  expanded,
  onToggle,
}: {
  action: ActionData;
  expanded: boolean;
  onToggle: () => void;
}) {
  const statusClass =
    a.status === 'allowed'
      ? 'badge-allow'
      : a.status === 'blocked'
      ? 'badge-block'
      : 'badge-approval';

  return (
    <>
      <tr
        className="border-b border-pact-border/50 hover:bg-pact-surface/40 cursor-pointer transition-colors"
        onClick={onToggle}
      >
        <td className="py-2 pr-3 text-gray-500">
          {expanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        </td>
        <td className="py-2 pr-3 font-mono text-gray-300">{a.step_id}</td>
        <td className="py-2 pr-3 font-mono text-pact-info">{a.tool}</td>
        <td className="py-2 pr-3">
          <span className={statusClass}>{a.status}</span>
        </td>
        <td className="py-2 pr-3 text-right font-mono">{a.policy_decision?.risk_score ?? '—'}</td>
        <td className="py-2 font-mono text-gray-400 truncate max-w-xs">
          {a.provenance.influenced_by.length > 0
            ? a.provenance.influenced_by.join(', ')
            : '—'}
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={6} className="bg-pact-bg/60 px-6 py-4 border-b border-pact-border/30">
            <div className="grid grid-cols-3 gap-6 text-xs">
              <div>
                <div className="text-gray-500 mb-1 font-medium">Policy Decision</div>
                {a.policy_decision ? (
                  <div className="space-y-1">
                    <div>
                      Decision: <span className={a.policy_decision.decision === 'BLOCK' ? 'text-red-400' : 'text-green-400'}>{a.policy_decision.decision}</span>
                    </div>
                    <div>Severity: <span className="text-gray-300">{a.policy_decision.severity}</span></div>
                    <div>Risk: <span className="font-mono">{a.policy_decision.risk_score}</span></div>
                    {a.policy_decision.reasons.length > 0 && (
                      <ul className="mt-1 space-y-0.5 list-disc list-inside text-gray-400">
                        {a.policy_decision.reasons.map((r, i) => (
                          <li key={i}>{r}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                ) : (
                  <span className="text-gray-500">No decision recorded</span>
                )}
              </div>

              <div>
                <div className="text-gray-500 mb-1 font-medium">Provenance</div>
                <div className="space-y-1">
                  <div>Influenced by: <span className="text-gray-300">{a.provenance.influenced_by.join(', ') || '—'}</span></div>
                  <div>Uses data: <span className="text-gray-300">{a.provenance.uses_data.join(', ') || '—'}</span></div>
                  <div>Side effect: <span className="text-gray-300">{a.provenance.side_effect ?? '—'}</span></div>
                </div>
              </div>

              <div>
                <div className="text-gray-500 mb-1 font-medium">Envelope</div>
                <pre className="text-[10px] text-gray-400 bg-pact-surface rounded p-2 overflow-auto max-h-32">
                  {JSON.stringify(
                    {
                      action_hash: a.action_hash,
                      intent_hash: a.intent_hash,
                      args_digest: a.args_digest,
                      parent_action_hash: a.parent_action_hash,
                    },
                    null,
                    2,
                  )}
                </pre>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="soc-card">
      <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">{label}</div>
      <div className="text-sm font-mono text-gray-200 truncate">{value}</div>
    </div>
  );
}
