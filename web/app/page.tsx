"use client";

import { AppShell } from "../components/app-shell/AppShell";
import { DemoStoryPicker } from "../components/features/demo/DemoStoryPicker";
import { OnboardingFlow } from "../components/features/onboarding/OnboardingFlow";
import { StoryList } from "../components/features/stories/StoryList";
import { VoiceAgentView } from "../components/features/voice/VoiceAgentView";
import { WorkspaceView } from "../components/features/workspace/WorkspaceView";
import { useClientRouter } from "../lib/client-router";
import { useDemoMode, useSelectedDemoStory } from "../lib/demo-mode";
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

/**
 * Demo mode reuses the real onboarding/workspace flow verbatim — same
 * `SeedForm`/`TemplatePicker`/`LanguagePicker`/`CastEditor`/`CastLock`/
 * `WorkspaceView`, same "Continue"/character-lock/chapter-tree UI a real
 * story gets. The only thing demo mode changes is which *story* you're
 * picking from first (a saved bundle instead of typing a fresh idea); once
 * picked, every API call those components make is transparently answered
 * from that saved bundle instead of the network (see `demo-runtime.ts`),
 * so the rest of the app underneath needs zero awareness that it's in demo
 * mode at all.
 */
function RouteOutlet() {
  const { pathname, navigate } = useClientRouter();
  const [demoMode] = useDemoMode();
  const [demoStoryId, setDemoStoryId] = useSelectedDemoStory();

  if (demoMode && !demoStoryId) {
    return (
      <section className="mx-auto max-w-3xl rounded-xl border border-stone-700 bg-[#191724] p-8">
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-violet-300">Demo mode</p>
        <h1 className="mt-3 text-2xl font-semibold">Choose a demo story</h1>
        <div className="mt-6">
          <DemoStoryPicker onSelect={setDemoStoryId} />
        </div>
      </section>
    );
  }

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
