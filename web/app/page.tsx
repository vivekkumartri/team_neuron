"use client";

import { useState } from "react";

import { AppShell } from "../components/app-shell/AppShell";
import { EndingOptionsView } from "../components/features/endings/EndingOptionsView";
import { OnboardingFlow } from "../components/features/onboarding/OnboardingFlow";
import { BusinessReportsView } from "../components/features/reports/BusinessReportsView";
import { TraceDrawer } from "../components/features/reports/TraceDrawer";
import { StoryList } from "../components/features/stories/StoryList";
import { WorkspaceView } from "../components/features/workspace/WorkspaceView";
import { WorldView } from "../components/features/world/WorldView";
import { useClientRouter } from "../lib/client-router";
import { useSelectedBranch } from "../lib/story-context";

/**
 * `/world`, `/endings`, and `/reports` still don't have a per-view story
 * picker of their own (only `/workspace` reads the shared "active branch"),
 * so they keep a plain text-box fallback for now — narrower gap than before,
 * where nothing in `app/page.tsx` had ever imported the real `StoryList`
 * picker at all.
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
  const { branchId } = useSelectedBranch();

  if (!branchId) {
    return (
      <section className="mx-auto max-w-2xl space-y-4 rounded-xl border border-stone-700 bg-[#191724] p-8">
        <h1 className="text-2xl font-semibold">Choose or create a story</h1>
        <p className="text-sm text-stone-300">
          Pick one of your stories below, or start a new one to create its first timeline.
        </p>
        <StoryList />
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
      <section className="mx-auto max-w-2xl space-y-8">
        <IdScopedView
          title="Business reports"
          placeholder="Branch ID"
          render={(id) => <BusinessReportsView branchId={id} />}
        />
        <IdScopedView
          title="Agent trace"
          placeholder="Agent run ID"
          render={(id) => <TraceDrawer runId={id} />}
        />
      </section>
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
