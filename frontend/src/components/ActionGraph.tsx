/**
 * ActionGraph — React Flow visualization of agent actions and policy decisions.
 */

import { useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import type { RunDetail as RunDetailType, ActionData } from '../api/client';

interface Props {
  run: RunDetailType;
}

const NODE_W = 180;
const NODE_H = 50;
const GAP_Y = 80;

function statusColor(status: string): string {
  if (status === 'allowed') return '#22c55e';
  if (status === 'blocked') return '#ef4444';
  return '#f59e0b';
}

function severityBg(severity: string): string {
  if (severity === 'critical') return '#ef4444';
  if (severity === 'high') return '#f97316';
  if (severity === 'medium') return '#f59e0b';
  return '#22c55e';
}

export default function ActionGraph({ run }: Props) {
  const { nodes, edges } = useMemo(() => {
    const n: Node[] = [];
    const e: Edge[] = [];

    // Create intent node
    n.push({
      id: 'intent',
      type: 'default',
      position: { x: 200, y: 0 },
      data: { label: `Intent: ${run.user_goal?.slice(0, 40) ?? 'Goal'}` },
      style: {
        background: '#7c3aed',
        color: '#fff',
        border: '1px solid #a78bfa',
        borderRadius: 8,
        fontSize: 11,
        padding: '8px 12px',
        width: NODE_W + 60,
      },
    });

    run.actions.forEach((a: ActionData, idx: number) => {
      const y = (idx + 1) * (NODE_H + GAP_Y);
      const color = statusColor(a.status);
      const bg = a.status === 'blocked' ? '#1a0505' : a.status === 'allowed' ? '#051a05' : '#1a1505';

      // Tool call node
      n.push({
        id: `action-${a.step_id}`,
        type: 'default',
        position: { x: 120, y },
        data: {
          label: (
            <div style={{ textAlign: 'center', lineHeight: 1.3 }}>
              <div style={{ fontWeight: 600, fontSize: 11 }}>{a.tool}</div>
              <div style={{ fontSize: 9, opacity: 0.7 }}>step {a.step_id} · {a.status}</div>
            </div>
          ),
        },
        style: {
          background: bg,
          color,
          border: `1px solid ${color}`,
          borderRadius: 8,
          width: NODE_W,
          height: NODE_H,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        },
      });

      // Edge from intent to first action, or parent chain
      const source = idx === 0 ? 'intent' : `action-${run.actions[idx - 1].step_id}`;
      e.push({
        id: `e-${source}-${a.step_id}`,
        source,
        target: `action-${a.step_id}`,
        label: 'calls_tool',
        labelStyle: { fill: color, fontSize: 9 },
        style: { stroke: color },
        markerEnd: { type: MarkerType.ArrowClosed, color },
        animated: a.status === 'blocked',
      });

      // Provenance source node (if any)
      if (a.provenance.influenced_by.length > 0) {
        const allLabels = a.provenance.influenced_by;
        const provId = `prov-${a.step_id}`;
        n.push({
          id: provId,
          type: 'default',
          position: { x: 400, y },
          data: {
            label: (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3, justifyContent: 'center' }}>
                {allLabels.map((label: string) => (
                  <span
                    key={label}
                    style={{
                      display: 'inline-block',
                      fontSize: 9,
                      padding: '1px 5px',
                      borderRadius: 4,
                      border: `1px solid ${label.startsWith('untrusted') ? '#ef444455' : '#22c55e55'}`,
                      background: label.startsWith('untrusted') ? '#1a0505' : '#051a05',
                      color: label.startsWith('untrusted') ? '#f87171' : '#86efac',
                    }}
                  >
                    {label}
                  </span>
                ))}
              </div>
            ),
          },
          style: {
            background: '#1a1000',
            color: '#f59e0b',
            border: '1px solid #f59e0b55',
            borderRadius: 8,
            fontSize: 10,
            width: 160,
            padding: '6px 10px',
          },
        });
        e.push({
          id: `e-${provId}-action-${a.step_id}`,
          source: provId,
          target: `action-${a.step_id}`,
          label: 'influenced_by',
          labelStyle: { fill: '#f59e0b', fontSize: 8 },
          style: { stroke: '#f59e0b55', strokeDasharray: '5 5' },
        });
      }

      // Uses-data edge (from action to its own provenance node)
      if (a.provenance.uses_data.length > 0 && a.provenance.influenced_by.length > 0) {
        const provId = `prov-${a.step_id}`;
        e.push({
          id: `e-action-${a.step_id}-uses-data`,
          source: `action-${a.step_id}`,
          target: provId,
          label: 'uses_data',
          labelStyle: { fill: '#3b82f6', fontSize: 8 },
          style: { stroke: '#3b82f655', strokeDasharray: '3 3' },
        });
      }

      // Policy decision node
      if (a.policy_decision) {
        const pdId = `pd-${a.step_id}`;
        const pdColor = severityBg(a.policy_decision.severity);
        n.push({
          id: pdId,
          type: 'default',
          position: { x: -100, y },
          data: { label: `${a.policy_decision.decision} (${a.policy_decision.risk_score})` },
          style: {
            background: a.policy_decision.decision === 'BLOCK' ? '#1a0505' : '#051a05',
            color: pdColor,
            border: `1px solid ${pdColor}55`,
            borderRadius: 8,
            fontSize: 10,
            width: 140,
            padding: '6px 10px',
          },
        });
        e.push({
          id: `e-action-${a.step_id}-${pdId}`,
          source: `action-${a.step_id}`,
          target: pdId,
          label: a.policy_decision.decision === 'BLOCK' ? 'blocked_by' : 'allowed_by',
          labelStyle: { fill: pdColor, fontSize: 8 },
          style: { stroke: `${pdColor}55` },
        });
      }
    });

    return { nodes: n, edges: e };
  }, [run]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      fitView
      proOptions={{ hideAttribution: true }}
      style={{ background: '#0a0e17' }}
    >
      <Background color="#1e293b" gap={20} size={1} />
      <Controls showInteractive={false} />
    </ReactFlow>
  );
}
