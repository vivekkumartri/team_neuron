"use client";

import { useEffect, useState } from "react";

import { AppShell } from "../components/app-shell/AppShell";
import { EndingOptionsView } from "../components/features/endings/EndingOptionsView";
import { OnboardingFlow } from "../components/features/onboarding/OnboardingFlow";
import { TraceDrawer } from "../components/features/reports/TraceDrawer";
import { WorldView } from "../components/features/world/WorldView";
import { useClientRouter } from "../lib/client-router";

const initialActivity = [
  ["Director", "Selecting a focal character and scene pressure."],
  ["World", "Checking continuity against this branch's canon."],
  ["Storyteller", "Drafting the next scene and dialogue."],
  ["Evaluator", "Reviewing the staged chapter before publication."],
];

function WorkspaceStudio() {
  const [active, setActive] = useState(0);
  const [activity, setActivity] = useState(initialActivity);

  useEffect(() => {
    const source = new EventSource("/api/v1/generation-events/demo");
    source.addEventListener("generation-progress", (message) => {
      const event = JSON.parse((message as MessageEvent<string>).data) as {
        agent: string;
        summary: string;
      };
      setActivity((current) => [...current, [event.agent, event.summary]]);
    });
    return () => source.close();
  }, []);

  return (
    <section className="mx-auto grid max-w-7xl gap-6 lg:grid-cols-[1fr_340px]">
      <article className="rounded-xl border border-stone-700 bg-[#191724] p-6">
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-violet-300">
          Chapter 2 · staged generation
        </p>
        <h2 className="mt-3 text-3xl font-semibold">The bridge remembers</h2>
        <p className="mt-5 max-w-2xl text-stone-300">
          Mara pauses at the broken bridge. The river below is loud enough to hide a warning, but
          not the choice ahead.
        </p>
        <div className="mt-8 grid gap-3 sm:grid-cols-3">
          <button className="rounded-lg bg-amber-300 px-4 py-3 font-medium text-stone-950">
            Continue
          </button>
          <button className="rounded-lg border border-violet-300 px-4 py-3 text-violet-100">
            Edit traits
          </button>
          <button className="rounded-lg border border-teal-300 px-4 py-3 text-teal-100">
            Jump / rewind
          </button>
        </div>
      </article>
      <aside aria-live="polite" className="rounded-xl border border-stone-700 bg-[#191724] p-4">
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-teal-300">
          Agent activity
        </p>
        <ol className="mt-4 space-y-3">
          {activity.map(([agent, note], index) => (
            <li
              key={`${agent}-${index}`}
              className={`rounded-lg border p-3 ${
                index === active ? "border-teal-300 bg-teal-950/30" : "border-stone-700"
              }`}
            >
              <button className="w-full text-left" onClick={() => setActive(index)}>
                <strong>{agent}</strong>
                <span className="mt-1 block text-sm text-stone-300">{note}</span>
              </button>
            </li>
          ))}
        </ol>
      </aside>
    </section>
  );
}

/**
 * There is no story/branch context provider yet (no UI has ever listed a
 * user's stories/branches and let them pick one) — that's a further gap
 * beyond this component. Until it exists, these views take their scoping id
 * from a plain text field so they're exercising the real backend routes
 * rather than being unreachable placeholders.
 */
function IdScopedView({
  title,
  placeholder,
  render,
}: {
  title: string;
  placeholder: string;
  render: (id: string) => React.ReactNode;
}) {
  const [id, setId] = useState("");
  return (
    <section className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-2xl font-semibold">{title}</h1>
      <label className="block text-sm">
        {placeholder}
        <input
          value={id}
          onChange={(event) => setId(event.target.value)}
          className="mt-1 w-full rounded-lg border border-stone-700 bg-[#11101a] p-2 font-mono text-sm"
          placeholder="00000000-0000-0000-0000-000000000000"
        />
      </label>
      {id && render(id)}
    </section>
  );
}

function RouteOutlet() {
  const { pathname, navigate } = useClientRouter();
  if (pathname === "/workspace") return <WorkspaceStudio />;
  if (pathname === "/world") {
    return (
      <IdScopedView title="World" placeholder="Branch ID" render={(id) => <WorldView branchId={id} />} />
    );
  }
  if (pathname === "/endings") {
    return (
      <IdScopedView
        title="Endings"
        placeholder="Branch ID"
        render={(id) => <EndingOptionsView branchId={id} />}
      />
    );
  }
  if (pathname === "/reports") {
    return (
      <IdScopedView
        title="Reports"
        placeholder="Agent run ID"
        render={(id) => <TraceDrawer runId={id} />}
      />
    );
  }
  return <OnboardingFlow onStoryReady={() => navigate("/workspace")} />;
}

export default function StudioPage() {
  return (
    <AppShell>
      <RouteOutlet />
    </AppShell>
  );
}
