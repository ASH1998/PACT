import {
  AlertTriangle,
  CheckCircle2,
  Fingerprint,
  GitBranch,
  KeyRound,
  LockKeyhole,
  Network,
  PenLine,
  Radar,
  Route,
  ShieldCheck,
  Tags,
  XCircle,
} from 'lucide-react';

const controls = [
  {
    name: 'Agent Passport',
    icon: Fingerprint,
    signal: 'Ed25519 identity',
    blocks: 'identity spoofing',
    status: 'enforced',
  },
  {
    name: 'Intent Contract',
    icon: Route,
    signal: 'user goal binding',
    blocks: 'goal drift',
    status: 'enforced',
  },
  {
    name: 'Capability Token',
    icon: KeyRound,
    signal: 'scoped short-lived permission',
    blocks: 'unauthorized access',
    status: 'enforced',
  },
  {
    name: 'Action Envelope',
    icon: PenLine,
    signal: 'signed tool request',
    blocks: 'raw tool calls',
    status: 'enforced',
  },
  {
    name: 'Provenance Labels',
    icon: Tags,
    signal: 'trusted, untrusted, secret',
    blocks: 'prompt injection flow',
    status: 'enforced',
  },
  {
    name: 'Hash-Chain Ledger',
    icon: GitBranch,
    signal: 'tamper-evident audit',
    blocks: 'silent misuse',
    status: 'verified',
  },
];

const threats = [
  {
    name: 'Prompt Injection',
    indicator: 'untrusted.web or untrusted.email influencing an external write',
    outcome: 'blocked at gateway',
    severity: 'critical',
  },
  {
    name: 'Identity Spoofing',
    indicator: 'agent has no valid passport or signature',
    outcome: 'blocked before policy',
    severity: 'critical',
  },
  {
    name: 'Unauthorized Access',
    indicator: 'capability token missing, expired, exhausted, or wrong resource',
    outcome: 'blocked before execution',
    severity: 'high',
  },
  {
    name: 'Adversarial Misuse',
    indicator: 'shell, secret, external write, or forbidden tool path',
    outcome: 'blocked or approval gated',
    severity: 'high',
  },
];

const pipeline = [
  'Agent request',
  'Passport',
  'Intent',
  'Capability',
  'Provenance',
  'Policy',
  'Ledger',
  'Tool',
];

export default function TrustArchitecture() {
  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-pact-accent mb-2">
            <Network className="w-4 h-4" />
            <span className="text-xs uppercase tracking-wider">Trust Architecture</span>
          </div>
          <h1 className="text-xl font-semibold tracking-tight">Agent Tool Calls Require Verifiable Context</h1>
        </div>
        <div className="flex items-center gap-2 rounded border border-green-500/30 bg-green-500/10 px-3 py-2 text-xs text-green-400">
          <ShieldCheck className="w-4 h-4" />
          Runtime enforcement active
        </div>
      </div>

      <div className="grid grid-cols-8 gap-2">
        {pipeline.map((step, index) => (
          <div key={step} className="min-w-0">
            <div className="h-16 rounded-lg border border-pact-border bg-pact-surface flex items-center justify-center px-2 text-center text-xs font-mono text-gray-200">
              {step}
            </div>
            {index < pipeline.length - 1 && (
              <div className="hidden" />
            )}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-4">
        <StatusTile icon={CheckCircle2} label="Safe Actions" value="Allow + audit" tone="green" />
        <StatusTile icon={XCircle} label="Unsafe Actions" value="Block before tool" tone="red" />
        <StatusTile icon={AlertTriangle} label="Sensitive Actions" value="Approval gate" tone="amber" />
      </div>

      <div>
        <h2 className="text-sm font-medium text-gray-300 mb-3">Control Plane</h2>
        <div className="grid grid-cols-3 gap-4">
          {controls.map(({ name, icon: Icon, signal, blocks, status }) => (
            <div key={name} className="soc-card">
              <div className="flex items-start justify-between gap-3">
                <Icon className="w-5 h-5 text-pact-accent" />
                <span className="rounded border border-green-500/30 bg-green-500/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-green-400">
                  {status}
                </span>
              </div>
              <div className="mt-3 text-sm font-medium text-gray-100">{name}</div>
              <div className="mt-2 space-y-1 text-xs">
                <div className="text-gray-500">Signal</div>
                <div className="font-mono text-gray-300">{signal}</div>
                <div className="pt-2 text-gray-500">Stops</div>
                <div className="font-mono text-pact-info">{blocks}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="soc-card">
          <div className="flex items-center gap-2 mb-3">
            <Radar className="w-4 h-4 text-pact-warning" />
            <h2 className="text-sm font-medium text-gray-300">Threat Coverage</h2>
          </div>
          <div className="space-y-3">
            {threats.map((threat) => (
              <div key={threat.name} className="border-b border-pact-border/60 pb-3 last:border-0 last:pb-0">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm text-gray-100">{threat.name}</div>
                  <span className={threat.severity === 'critical' ? 'badge-block' : 'badge-approval'}>
                    {threat.severity}
                  </span>
                </div>
                <div className="mt-1 text-xs text-gray-500">{threat.indicator}</div>
                <div className="mt-1 text-xs font-mono text-green-400">{threat.outcome}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="soc-card">
          <div className="flex items-center gap-2 mb-3">
            <LockKeyhole className="w-4 h-4 text-pact-accent" />
            <h2 className="text-sm font-medium text-gray-300">Demo Proof Points</h2>
          </div>
          <div className="space-y-3 text-xs">
            <ProofPoint label="Identity" value="Fake agents fail passport verification before a tool runs." />
            <ProofPoint label="Intent" value="An email summary goal cannot send email to an attacker." />
            <ProofPoint label="Capability" value="Expired or mismatched tokens are rejected by the gateway." />
            <ProofPoint label="Provenance" value="Untrusted web/email data cannot drive external writes." />
            <ProofPoint label="Monitoring" value="Risk scores, blocked tools, provenance sources, replay, and ledger state are visible in the SOC." />
          </div>
        </div>
      </div>
    </div>
  );
}

function StatusTile({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: typeof CheckCircle2;
  label: string;
  value: string;
  tone: 'green' | 'red' | 'amber';
}) {
  const color = tone === 'green' ? 'text-green-400' : tone === 'red' ? 'text-red-400' : 'text-amber-400';
  const border = tone === 'green' ? 'border-green-500/30' : tone === 'red' ? 'border-red-500/30' : 'border-amber-500/30';

  return (
    <div className={`soc-card border ${border}`}>
      <Icon className={`w-5 h-5 ${color}`} />
      <div className="mt-3 text-xs uppercase tracking-wider text-gray-500">{label}</div>
      <div className="mt-1 text-sm font-mono text-gray-100">{value}</div>
    </div>
  );
}

function ProofPoint({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[110px_1fr] gap-3 border-b border-pact-border/60 pb-3 last:border-0 last:pb-0">
      <div className="font-mono text-pact-info">{label}</div>
      <div className="text-gray-300">{value}</div>
    </div>
  );
}
