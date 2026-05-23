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
} from 'lucide-react';
import { getReplay, ReplayData, ReplayStepData } from '../api/client';

export default function Replay() {
  const { runId } = useParams<{ runId: string }>();
  const [data, setData] = useState<ReplayData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [current, setCurrent] = useState(0);
  const [playing, setPlaying] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!runId) return;
    getReplay(runId)
      .then(setData)
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

function StepDetail({ step }: { step: ReplayStepData }) {
  const pd = step.policy_decision;
  const isBlocked = pd.decision === 'BLOCK';

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

      {/* Metadata grid */}
      <div className="grid grid-cols-2 gap-4 text-xs">
        <Field label="Timestamp" value={step.timestamp ? new Date(step.timestamp).toLocaleString() : '—'} />
        <Field label="Agent" value={step.agent_id} />
        <Field label="Risk Score" value={String(pd.risk_score)} />
        <Field label="Severity" value={pd.severity} />
        <Field label="Action Hash" value={step.action_hash} mono />
        <Field label="Parent Hash" value={step.parent_action_hash ?? '—'} mono />
      </div>

      {/* Provenance */}
      <Section title="Provenance">
        <div className="text-xs space-y-1">
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
      </Section>

      {/* Policy reasons */}
      <Section title="Policy Decision Reasons">
        {pd.reasons.length === 0 ? (
          <div className="text-gray-500 text-xs">No reasons</div>
        ) : (
          <ul className="text-xs space-y-1">
            {pd.reasons.map((r, i) => (
              <li key={i} className="flex items-start gap-1.5">
                <span className="text-gray-500">•</span>
                <span className="text-gray-300">{r}</span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      {/* Integrity */}
      <Section title="Integrity">
        <div className="flex gap-4 text-xs">
          <span className={step.signature_valid ? 'text-green-400' : 'text-red-400'}>
            {step.signature_valid ? '✓ Signature valid' : '✗ Signature invalid'}
          </span>
          <span className={step.chain_valid ? 'text-green-400' : 'text-red-400'}>
            {step.chain_valid ? '✓ Chain valid' : '✗ Chain broken'}
          </span>
        </div>
      </Section>

      {/* Envelope JSON */}
      <Section title="Envelope JSON">
        <pre className="text-[10px] text-gray-400 bg-pact-bg rounded p-3 overflow-auto max-h-48 font-mono">
          {JSON.stringify(step.envelope, null, 2)}
        </pre>
      </Section>
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <div className="text-[10px] text-gray-500 uppercase tracking-wider">{label}</div>
      <div className={`text-sm text-gray-200 truncate ${mono ? 'font-mono text-xs' : ''}`}>{value}</div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs font-medium text-gray-400 mb-2">{title}</div>
      {children}
    </div>
  );
}
