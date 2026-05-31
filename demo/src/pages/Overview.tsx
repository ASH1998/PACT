import { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  Fingerprint,
  GitBranch,
  KeyRound,
  Loader2,
  PenLine,
  Play,
  Route,
  Shield,
  Tags,
  XCircle,
  Zap,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import {
  getDashboardOverview,
  DashboardOverview,
  getScenarios,
  runScenario,
  ScenarioInfo,
  ScenarioRunResponse,
  getBlockedActions,
  BlockedActionData,
} from '../api/client';

export default function Overview() {
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([]);
  const [runningName, setRunningName] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<ScenarioRunResponse | null>(null);
  const [runError, setRunError] = useState('');
  const [blocked, setBlocked] = useState<BlockedActionData[]>([]);

  const fetchDashboard = useCallback(async () => {
    try {
      const [overview, blockedActions] = await Promise.all([
        getDashboardOverview(),
        getBlockedActions(),
      ]);
      setData(overview);
      setBlocked(blockedActions);
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
    getScenarios().then(setScenarios).catch(() => {});
    const id = window.setInterval(fetchDashboard, 3000);
    return () => window.clearInterval(id);
  }, [fetchDashboard]);

  async function handleRun(name: string) {
    setRunningName(name);
    setLastResult(null);
    setRunError('');
    try {
      const result = await runScenario(name);
      setLastResult(result);
      fetchDashboard();
    } catch (e: unknown) {
      setRunError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunningName(null);
    }
  }

  if (loading) return <Skeleton />;
  if (error) return <div className="text-red-400 text-sm p-8">Error: {error}</div>;
  if (!data) return null;

  const cards = [
    { label: 'Total Runs', value: data.total_runs, icon: Shield, color: 'text-pact-accent' },
    { label: 'Allowed Actions', value: data.allowed_actions, icon: CheckCircle, color: 'text-pact-success' },
    { label: 'Blocked Actions', value: data.blocked_actions, icon: XCircle, color: 'text-pact-danger' },
    { label: 'Critical Events', value: data.critical_events, icon: AlertTriangle, color: 'text-pact-warning' },
  ];

  const timeline = [...data.risk_timeline]
    .reverse()
    .map((d, i) => ({
      name: d.timestamp ? new Date(d.timestamp).toLocaleTimeString() : `#${i}`,
      risk: d.risk_score,
      severity: d.severity,
    }));

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-pact-accent mb-2">
            <Shield className="w-4 h-4" />
            <span className="text-xs uppercase tracking-wider">Agent Security Operations</span>
          </div>
          <h1 className="text-xl font-semibold tracking-tight">Trust Monitor</h1>
        </div>
        <div className="rounded border border-pact-border bg-pact-surface px-3 py-2 text-xs">
          <div className="text-gray-500">Runtime Decision Point</div>
          <div className="font-mono text-green-400">PACT Gateway</div>
        </div>
      </div>

      <div className="grid grid-cols-6 gap-3">
        <TrustSignal icon={Fingerprint} label="Identity" value="passport" />
        <TrustSignal icon={Route} label="Intent" value="goal lock" />
        <TrustSignal icon={KeyRound} label="Capability" value="scoped token" />
        <TrustSignal icon={Tags} label="Provenance" value="taint flow" />
        <TrustSignal icon={PenLine} label="Policy" value="allow/block" />
        <TrustSignal icon={GitBranch} label="Ledger" value="hash chain" />
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-4 gap-4">
        {cards.map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="soc-card flex items-center gap-3">
            <Icon className={`w-8 h-8 ${color}`} />
            <div>
              <div className="text-2xl font-bold font-mono">{value}</div>
              <div className="text-xs text-gray-400">{label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Run Scenario */}
      <div className="soc-card">
        <div className="flex items-center gap-2 mb-4">
          <Zap className="w-4 h-4 text-pact-accent" />
          <h2 className="text-sm font-medium text-gray-300">Run Scenario</h2>
        </div>
        {scenarios.length === 0 ? (
          <div className="text-gray-500 text-xs py-4 text-center">Loading scenarios…</div>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            {scenarios.map((s) => {
              const isRunning = runningName === s.name;
              return (
                <button
                  key={s.name}
                  onClick={() => handleRun(s.name)}
                  disabled={runningName !== null}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded border transition-colors text-left
                    ${isRunning
                      ? 'border-pact-accent bg-pact-accent/10'
                      : 'border-pact-border bg-pact-surface hover:border-pact-accent/60 hover:bg-pact-surface/80'}
                    disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                  {isRunning ? (
                    <Loader2 className="w-4 h-4 text-pact-accent animate-spin flex-shrink-0" />
                  ) : (
                    <Play className="w-4 h-4 text-pact-accent flex-shrink-0" />
                  )}
                  <div className="min-w-0">
                    <div className="text-xs font-medium text-gray-200 truncate">
                      {s.name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                    </div>
                    <div className="text-[10px] text-gray-500 truncate">{s.description}</div>
                  </div>
                </button>
              );
            })}
          </div>
        )}

        {/* Run result */}
        {lastResult && (
          <div className="mt-3 rounded border border-pact-border bg-pact-bg/60 p-3">
            <div className="flex items-center gap-2 mb-2">
              <Shield className="w-4 h-4 text-pact-success" />
              <span className="text-xs font-medium text-gray-200">
                {lastResult.scenario_name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())} — Results
              </span>
            </div>
            <div className="grid grid-cols-4 gap-3 text-center">
              <div>
                <div className="text-lg font-bold font-mono text-gray-100">{lastResult.total_actions}</div>
                <div className="text-[10px] text-gray-500">Total</div>
              </div>
              <div>
                <div className="text-lg font-bold font-mono text-pact-success">{lastResult.allowed_actions}</div>
                <div className="text-[10px] text-gray-500">Allowed</div>
              </div>
              <div>
                <div className="text-lg font-bold font-mono text-pact-danger">{lastResult.blocked_actions}</div>
                <div className="text-[10px] text-gray-500">Blocked</div>
              </div>
              <div>
                <div className={`text-lg font-bold font-mono ${lastResult.max_risk_score >= 70 ? 'text-pact-danger' : lastResult.max_risk_score >= 40 ? 'text-pact-warning' : 'text-pact-success'}`}>
                  {lastResult.max_risk_score}
                </div>
                <div className="text-[10px] text-gray-500">Max Risk</div>
              </div>
            </div>
          </div>
        )}
        {runError && (
          <div className="mt-2 text-xs text-red-400 flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5" />
            {runError}
          </div>
        )}
      </div>

      {/* Risk timeline chart */}
      <div className="soc-card">
        <h2 className="text-sm font-medium mb-4 text-gray-300">Risk Timeline</h2>
        {timeline.length === 0 ? (
          <div className="text-gray-500 text-xs py-8 text-center">No data yet</div>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={timeline}>
              <defs>
                <linearGradient id="riskGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#6b7280' }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#6b7280' }} />
              <Tooltip
                contentStyle={{ background: '#111827', border: '1px solid #1e293b', borderRadius: 6, fontSize: 12 }}
                labelStyle={{ color: '#9ca3af' }}
              />
              <Area type="monotone" dataKey="risk" stroke="#ef4444" fill="url(#riskGrad)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Tables row */}
      <div className="grid grid-cols-2 gap-4">
        {/* Top attacked tools */}
        <div className="soc-card">
          <h2 className="text-sm font-medium mb-3 text-gray-300">Top Attacked Tools</h2>
          {data.top_attacked_tools.length === 0 ? (
            <div className="text-gray-500 text-xs py-4 text-center">No data</div>
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-gray-500 border-b border-pact-border">
                  <th className="text-left py-1.5 font-medium">Tool</th>
                  <th className="text-right py-1.5 font-medium">Blocks</th>
                </tr>
              </thead>
              <tbody>
                {data.top_attacked_tools.map((t) => (
                  <tr key={t.tool} className="border-b border-pact-border/50">
                    <td className="py-1.5 font-mono text-pact-info">{t.tool}</td>
                    <td className="py-1.5 text-right font-mono text-pact-danger">{t.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Provenance sources */}
        <div className="soc-card">
          <h2 className="text-sm font-medium mb-3 text-gray-300">Top Provenance Sources</h2>
          {data.top_provenance_sources.length === 0 ? (
            <div className="text-gray-500 text-xs py-4 text-center">No data</div>
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-gray-500 border-b border-pact-border">
                  <th className="text-left py-1.5 font-medium">Source</th>
                  <th className="text-right py-1.5 font-medium">Count</th>
                </tr>
              </thead>
              <tbody>
                {data.top_provenance_sources.map((s) => (
                  <tr key={s.source} className="border-b border-pact-border/50">
                    <td className="py-1.5 font-mono text-pact-info">{s.source}</td>
                    <td className="py-1.5 text-right font-mono">{s.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Recent Blocked Actions */}
      <div className="soc-card">
        <h2 className="text-sm font-medium mb-3 text-gray-300">Recent Blocked Actions</h2>
        {blocked.length === 0 ? (
          <div className="text-gray-500 text-xs py-4 text-center">No blocked actions</div>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-500 border-b border-pact-border">
                <th className="text-left py-1.5 font-medium">Run</th>
                <th className="text-left py-1.5 font-medium">Tool</th>
                <th className="text-left py-1.5 font-medium">Severity</th>
                <th className="text-right py-1.5 font-medium">Risk</th>
                <th className="text-left py-1.5 font-medium">Reason</th>
              </tr>
            </thead>
            <tbody>
              {blocked.slice(0, 10).map((b, i) => (
                <tr key={i} className="border-b border-pact-border/50">
                  <td className="py-1.5 font-mono text-pact-info">{b.run_id.slice(0, 10)}…</td>
                  <td className="py-1.5 font-mono text-gray-300">{b.tool}</td>
                  <td className="py-1.5"><span className={b.severity === 'critical' ? 'text-red-400' : b.severity === 'high' ? 'text-orange-400' : 'text-yellow-400'}>{b.severity}</span></td>
                  <td className="py-1.5 text-right font-mono">{b.risk_score}</td>
                  <td className="py-1.5 text-gray-400 truncate max-w-xs">{b.reasons.join(' | ') || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

/* Simple skeleton placeholder */
function Skeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-5 w-40 bg-pact-surface rounded" />
      <div className="grid grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="soc-card h-20" />
        ))}
      </div>
      <div className="soc-card h-60" />
    </div>
  );
}

function TrustSignal({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Shield;
  label: string;
  value: string;
}) {
  return (
    <div className="soc-card min-h-[88px]">
      <Icon className="w-4 h-4 text-pact-accent" />
      <div className="mt-3 text-[10px] uppercase tracking-wider text-gray-500">{label}</div>
      <div className="mt-1 text-xs font-mono text-gray-200">{value}</div>
    </div>
  );
}
