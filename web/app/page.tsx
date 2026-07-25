"use client";

import { useEffect, useState } from "react";

import { AppShell } from "../components/app-shell/AppShell";
import { EndingOptionsView } from "../components/features/endings/EndingOptionsView";
import { OnboardingFlow } from "../components/features/onboarding/OnboardingFlow";
import { TraceDrawer } from "../components/features/reports/TraceDrawer";
import { WorkspaceView } from "../components/features/workspace/WorkspaceView";
import { WorldView } from "../components/features/world/WorldView";
import { useClientRouter } from "../lib/client-router";

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

function WorkspaceRoute() {
  const [branchId, setBranchId] = useState<string | null>(null);

  useEffect(() => {
    setBranchId(window.localStorage.getItem("story-engine-active-branch"));
  }, []);

  if (!branchId) {
    return (
      <section className="mx-auto max-w-2xl rounded-xl border border-stone-700 bg-[#191724] p-8">
        <h1 className="text-2xl font-semibold">Choose or create a story</h1>
        <p className="mt-2 text-sm text-stone-300">
          Start a story to create its first timeline. Existing-story selection will appear here once
          a story has been opened in this browser.
        </p>
      </section>
    );
  }
  return <WorkspaceView branchId={branchId} />;
}

function RouteOutlet() {
  const { pathname, navigate } = useClientRouter();
  if (pathname === "/workspace") {
    return <WorkspaceRoute />;
  }
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
