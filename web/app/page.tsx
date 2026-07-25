"use client";

import { useEffect, useState } from "react";

const initialActivity = [
  ["Director", "Selecting a focal character and scene pressure."],
  ["World", "Checking continuity against this branch's canon."],
  ["Storyteller", "Drafting the next scene and dialogue."],
  ["Evaluator", "Reviewing the staged chapter before publication."],
];

export default function StudioPage() {
  const [active, setActive] = useState(0);
  const [activity, setActivity] = useState(initialActivity);

  useEffect(() => {
    const source = new EventSource("/api/v1/generation-events/demo");
    source.addEventListener("generation-progress", (message) => {
      const event = JSON.parse((message as MessageEvent<string>).data) as { agent: string; summary: string };
      setActivity((current) => [...current, [event.agent, event.summary]]);
    });
    return () => source.close();
  }, []);
  return <main className="min-h-screen bg-[#11101a] p-4 text-stone-100 md:p-8">
    <header className="mx-auto flex max-w-7xl items-center justify-between border-b border-stone-700 pb-4">
      <div><p className="font-mono text-xs uppercase tracking-[0.2em] text-teal-300">Story Engine</p><h1 className="text-2xl font-semibold">Narrative Studio</h1></div>
      <span className="rounded-full border border-amber-300 px-3 py-1 text-sm text-amber-200">Text MVP · Dev</span>
    </header>
    <section className="mx-auto mt-8 grid max-w-7xl gap-6 lg:grid-cols-[240px_1fr_340px]">
      <nav aria-label="Story navigation" className="rounded-xl border border-stone-700 bg-[#191724] p-4">
        <p className="font-mono text-xs text-stone-400">CURRENT BRANCH</p><p className="mt-2 font-semibold">Storm path</p>
        <ul className="mt-6 space-y-2 text-sm"><li>Story overview</li><li>Read chapter</li><li>Entity relationships</li><li>Canon events</li></ul>
      </nav>
      <article className="rounded-xl border border-stone-700 bg-[#191724] p-6">
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-violet-300">Chapter 2 · staged generation</p>
        <h2 className="mt-3 text-3xl font-semibold">The bridge remembers</h2>
        <p className="mt-5 max-w-2xl text-stone-300">Mara pauses at the broken bridge. The river below is loud enough to hide a warning, but not the choice ahead.</p>
        <div className="mt-8 grid gap-3 sm:grid-cols-3">
          <button className="rounded-lg bg-amber-300 px-4 py-3 font-medium text-stone-950">Continue</button>
          <button className="rounded-lg border border-violet-300 px-4 py-3 text-violet-100">Edit traits</button>
          <button className="rounded-lg border border-teal-300 px-4 py-3 text-teal-100">Jump / rewind</button>
        </div>
      </article>
      <aside aria-live="polite" className="rounded-xl border border-stone-700 bg-[#191724] p-4">
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-teal-300">Agent activity</p>
        <ol className="mt-4 space-y-3">{activity.map(([agent, note], index) => <li key={`${agent}-${index}`} className={`rounded-lg border p-3 ${index === active ? "border-teal-300 bg-teal-950/30" : "border-stone-700"}`}><button className="w-full text-left" onClick={() => setActive(index)}><strong>{agent}</strong><span className="mt-1 block text-sm text-stone-300">{note}</span></button></li>)}</ol>
      </aside>
    </section>
  </main>;
}
