"use client";

import type { GenerationActivityEvent } from "../../../lib/generation-stream";

const agents = [
  { id: "director", label: "Director", x: 50, y: 16, tone: "amber" },
  { id: "world", label: "World", x: 18, y: 50, tone: "teal" },
  { id: "character", label: "Character", x: 18, y: 84, tone: "violet" },
  { id: "storyteller", label: "Storyteller", x: 82, y: 50, tone: "violet" },
  { id: "evaluator", label: "Evaluator", x: 82, y: 84, tone: "teal" },
];

const edges = [
  ["director", "world"],
  ["world", "storyteller"],
  ["storyteller", "evaluator"],
  ["evaluator", "director"],
  ["character", "director"],
] as const;

export function AgentCoordinationCanvas({ events }: { events: GenerationActivityEvent[] }) {
  const latest = events.at(-1);
  const activeEdge = latest?.recipient_agent ? `${latest.agent}:${latest.recipient_agent}` : null;

  return (
    <section aria-label="Live agent coordination" className="rounded-lg border border-stone-700 bg-[#11101a] p-3">
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <p className="font-mono text-xs uppercase tracking-[0.14em] text-teal-300">Live coordination</p>
        <span className="text-xs text-stone-400">Director coordinates the loop</span>
      </div>
      <div className="relative aspect-[1.5] min-h-48">
        <svg aria-hidden="true" className="absolute inset-0 h-full w-full overflow-visible" viewBox="0 0 100 100">
          <defs>
            <marker id="agent-arrow" markerHeight="5" markerWidth="5" orient="auto" refX="4" refY="2.5">
              <path d="M0,0 L5,2.5 L0,5 Z" fill="currentColor" />
            </marker>
          </defs>
          {edges.map(([from, to]) => {
            const source = agents.find((agent) => agent.id === from)!;
            const target = agents.find((agent) => agent.id === to)!;
            const active = activeEdge === `${from}:${to}`;
            return (
              <line
                key={`${from}:${to}`}
                x1={source.x}
                y1={source.y}
                x2={target.x}
                y2={target.y}
                markerEnd="url(#agent-arrow)"
                className={active ? "animate-pulse text-amber-300" : "text-stone-600"}
                stroke="currentColor"
                strokeDasharray={active ? "0" : "2 2"}
                strokeWidth={active ? "1.4" : "0.7"}
              />
            );
          })}
        </svg>
        {agents.map((agent) => {
          const active = latest?.agent === agent.id || latest?.recipient_agent === agent.id;
          const colors = agent.tone === "amber" ? "border-amber-300 text-amber-100" : agent.tone === "teal" ? "border-teal-300 text-teal-100" : "border-violet-300 text-violet-100";
          return (
            <div
              key={agent.id}
              className={`absolute -translate-x-1/2 -translate-y-1/2 rounded-full border bg-[#191724] px-3 py-2 text-center text-xs shadow-lg ${colors} ${active ? "ring-2 ring-amber-300/60" : ""}`}
              style={{ left: `${agent.x}%`, top: `${agent.y}%` }}
            >
              <strong className="block">{agent.label}</strong>
              <span className="text-[10px] text-stone-300">{agent.id === "director" ? "Coordinator" : "Agent"}</span>
            </div>
          );
        })}
      </div>
      <p aria-live="polite" className="mt-2 min-h-5 text-xs text-stone-300">
        {latest?.recipient_agent
          ? `${latest.agent} is coordinating with ${latest.recipient_agent}: ${latest.summary}`
          : latest?.summary ?? "Waiting for a generation job to start."}
      </p>
    </section>
  );
}
