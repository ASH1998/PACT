import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  RotateCcw,
  CheckCircle,
  XCircle,
  Shield,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { getReplay, getRun, ReplayData, ReplayStepData, RunDetail as RunDetailType } from '../api/client';
import ActionGraph from '../components/ActionGraph';

export default function Replay() {
  const { runId } = useParams<{ runId: string }>();
  const [data, setData] = useState<ReplayData | null>(null);
  const [runDetail, setRunDetail] = useState<RunDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [current, setCurrent] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [showGraph, setShowGraph] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!runId) return;
    Promise.all([
      getReplay(runId),
      getRun(runId).catch(() => null),
    ])
      .then(([replay, run]) => {
        setData(replay);
        setRunDetail(run);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [runId]);

  const steps = data?.steps ?? [];
  const total = steps.length;

  const stop = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setPlaying(false);
  }, []);

  useEffect(() => {
    if (playing && total > 0) {
      timerRef.current = setInterval(() => {
        setCurrent((prev) => {
          if (prev >= total - 1) {
            stop();
            return prev;
          }
          return prev + 1;
        });
      }, 1000);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [playing, total, stop]);

  if (loading) return <div className="text-gray-400 text-sm p-8">Loading replay…</div>;
  if (error) return <div className="text-red-400 text-sm p-8">Error: {error}</div>;
  if (!data || steps.length === 0) {
    return (
      <div className="text-gray-500 text-sm p-8">
        <Link to={`/runs/${runId}`} className="text-pact-accent hover:underline text-xs">← Back</Link>
        <div className="mt-4">No replay data available for this run.</div>
      </div>
    );
  }

  const step = steps[current];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <Link to={`/runs/${runId}`} className="text-xs text-pact-accent hover:underline">
            ← Back to Run
          </Link>
          <h1 className="text-lg font-semibold tracking-tight mt-1">
            Replay: <span className="font-mono text-pact-info">{data.scenario_name ?? runId}</span>
          </h1>
        </div>
        <div className="text-xs text-gray-500 font-mono">
          {current + 1} / {total} steps
        </div>
      </div>

      {/* Action Graph (collapsible) */}
      {runDetail && (
        <div>
          <button
            onClick={() => setShowGraph(!showGraph)}
            className="text-xs text-pact-accent hover:underline flex items-center gap-1"
          >
            {showGraph ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            {showGraph ? 'Hide' : 'Show'} Action Graph
          </button>
          {showGraph && (
            <div className="soc-card mt-2" style={{ height: 360 }}>
              <ActionGraph run={runDetail} />
            </div>
          )}
        </div>
      )}

      <div className="flex gap-4" style={{ minHeight: 500 }}>
        {/* Timeline (left) */}
        <div className="w-56 shrink-0 space-y-1 overflow-y-auto" style={{ maxHeight: 500 }}>
          {steps.map((s, i) => {
            const isCurrent = i === current;
            const isBlocked = s.policy_decision.decision === 'BLOCK';
            return (
              <button
                key={s.step_id}
                onClick={() => setCurrent(i)}
                className={`w-full text-left px-3 py-2 rounded text-xs flex items-center gap-2 transition-colors ${
                  isCurrent
                    ? 'bg-pact-accent/15 border border-pact-accent/30'
                    : 'hover:bg-pact-surface border border-transparent'
                }`}
              >
                <span className="font-mono text-gray-500 w-5">{s.step_id}</span>
                {isBlocked ? (
                  <XCircle className="w-3.5 h-3.5 text-red-400 shrink-0" />
                ) : (
                  <CheckCircle className="w-3.5 h-3.5 text-green-400 shrink-0" />
                )}
                <span className={`truncate ${isCurrent ? 'text-white' : 'text-gray-400'}`}>
                  {s.tool}
                </span>
              </button>
            );
          })}
        </div>

        {/* Detail panel (right) */}
        <div className="flex-1 soc-card overflow-y-auto" style={{ maxHeight: 500 }}>
          <StepDetail step={step} />
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center justify-center gap-2">
        <CtrlBtn onClick={() => { stop(); setCurrent(0); }} icon={RotateCcw} label="Restart" />
        <CtrlBtn onClick={() => { stop(); setCurrent(Math.max(0, current - 1)); }} icon={SkipBack} label="Previous" />
        <button
          onClick={() => setPlaying(!playing)}
          className="flex items-center gap-1.5 px-4 py-2 bg-pact-accent/20 text-pact-accent rounded text-xs hover:bg-pact-accent/30 transition-colors"
        >
          {playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
          {playing ? 'Pause' : 'Play'}
        </button>
        <CtrlBtn onClick={() => { stop(); setCurrent(Math.min(total - 1, current + 1)); }} icon={SkipForward} label="Next" />
      </div>
    </div>
  );
}

function CtrlBtn({
  onClick,
  icon: Icon,
  label,
}: {
  onClick: () => void;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      title={label}
      className="p-2 rounded bg-pact-surface border border-pact-border hover:bg-pact-border/50 transition-colors"
    >
      <Icon className="w-4 h-4 text-gray-400" />
    </button>
  );
}

/* ---------- Narrative generation ---------- */

function getStepNarrative(step: ReplayStepData): string[] {
  const events: string[] = [];

  // What the agent is doing
  events.push(`Agent calls ${step.tool}`);

  // What data influenced it
  if (step.provenance?.influenced_by?.length) {
    const labels = step.provenance.influenced_by;
    const untrusted = labels.filter((l: string) => l.startsWith('untrusted.'));
    if (untrusted.length) {
      events.push(`⚠️ Influenced by ${untrusted.join(', ')}`);
    }
  }

  // Policy decision
  events.push(`Policy: ${step.policy_decision.decision} (risk: ${step.policy_decision.risk_score})`);

  // Reasons
  if (step.policy_decision.reasons?.length) {
    step.policy_decision.reasons.forEach((r: string) => events.push(`→ ${r}`));
  }

  // Integrity
  events.push(`Signature: ${step.signature_valid ? '✅ valid' : '❌ invalid'}`);
  events.push(`Chain: ${step.chain_valid ? '✅ intact' : '❌ broken'}`);

  return events;
}

/* ---------- Step detail with narrative ---------- */

function StepDetail({ step }: { step: ReplayStepData }) {
  const pd = step.policy_decision;
  const isBlocked = pd.decision === 'BLOCK';
  const narrative = getStepNarrative(step);
  const [showEnvelope, setShowEnvelope] = useState(false);
  const [showProvenance, setShowProvenance] = useState(false);

  return (
    <div className="space-y-5">
      {/* Step header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="w-5 h-5 text-pact-accent" />
          <span className="text-sm font-medium">Step {step.step_id}: {step.tool}</span>
        </div>
        <span className={isBlocked ? 'badge-block' : 'badge-allow'}>{pd.decision}</span>
      </div>

      {/* Narrative events card */}
      <div className="soc-card">
        <div className="text-xs font-medium text-gray-400 mb-2">Protocol Events</div>
        <ul className="space-y-1.5">
          {native_map(narrative)}
        </ul>
      </div>

      {/* Metadata grid */}
      <div className="grid grid-cols-2 gap-4 text-xs">
        <Field label="Timestamp" value={step.timestamp ? new Date(step.timestamp).toLocaleString() : '—'} />
        <Field label="Agent" value={step.agent_id} />
        <Field label="Risk Score" value={String(pd.risk_score)} />
        <Field label="Severity" value={pd.severity} />
        <Field label="Action Hash" value={step.action_hash} mono />
        <Field label="Parent Hash" value={step.parent_action_hash ?? '—'} mono />
      </div>

      {/* Provenance (expandable) */}
      <div>
        <button
          onClick={() => setShowProvenance(!showProvenance)}
          className="text-xs text-pact-accent hover:underline flex items-center gap-1"
        >
          {showProvenance ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          Provenance Details
        </button>
        {showProvenance && (
          <div className="mt-2 text-xs space-y-1 pl-4 border-l border-pact-border/30">
            <div>
              <span className="text-gray-500">Influenced by:</span>{' '}
              <span className="text-gray-300">{step.provenance.influenced_by.join(', ') || '—'}</span>
            </div>
            <div>
              <span className="text-gray-500">Uses data:</span>{' '}
              <span className="text-gray-300">{step.provenance.uses_data.join(', ') || '—'}</span>
            </div>
            <div>
              <span className="text-gray-500">Side effect:</span>{' '}
              <span className="text-gray-300">{step.provenance.side_effect ?? '—'}</span>
            </div>
          </div>
        )}
      </div>

      {/* Envelope JSON (expandable) */}
      <div>
        <button
          onClick={() => setShowEnvelope(!showEnvelope)}
          className="text-xs text-pact-accent hover:underline flex items-center gap-1"
        >
          {showEnvelope ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          Envelope JSON
        </button>
        {showEnvelope && (
          <pre className="mt-2 text-[10px] text-gray-400 bg-pact-bg rounded p-3 overflow-auto max-h-48 font-mono">
            {JSON.stringify(step.envelope, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}

function native_map(narrative: string[]) {
  return narrative.map((event, i) => {
    const isWarning = event.startsWith('⚠️');
    const isDecision = event.startsWith('Policy:');
    const isReason = event.startsWith('→');
    const isSigOk = event.includes('✅');
    const isSigBad = event.includes('❌');

    let colorClass = 'text-gray-300';
    if (isWarning) colorClass = 'text-yellow-400';
    else if (isDecision) colorClass = 'text-blue-300';
    else if (isReason) colorClass = 'text-gray-400';
    else if (isSigBad) colorClass = 'text-red-400';
    else if (isSigOk) colorClass = 'text-green-400';

    return (
      <li key={i} className={`text-xs ${colorClass} flex items-start gap-1.5`}>
        <span className="text-gray-600 shrink-0">•</span>
        <span>{event}</span>
      </li>
    );
  });
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <div className="text-[10px] text-gray-500 uppercase tracking-wider">{label}</div>
      <div className={`text-sm text-gray-200 truncate ${mono ? 'font-mono text-xs' : ''}`}>{value}</div>
    </div>
  );
}
