"use client";

import { AppShell } from "../components/app-shell/AppShell";
import { OnboardingFlow } from "../components/features/onboarding/OnboardingFlow";
import { StoryList } from "../components/features/stories/StoryList";
import { VoiceAgentView } from "../components/features/voice/VoiceAgentView";
import { WorkspaceView } from "../components/features/workspace/WorkspaceView";
import { useClientRouter } from "../lib/client-router";
import { useSelectedBranch } from "../lib/story-context";

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
  if (pathname === "/voice") {
    return <VoiceAgentView />;
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
