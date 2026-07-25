"use client";

import { useState } from "react";

import { CastLock } from "./CastLock";
import { SeedForm } from "./SeedForm";
import { TemplatePicker } from "./TemplatePicker";
import { PersonalizationConsent } from "../preferences/PersonalizationConsent";

type Step = "seed" | "template" | "personalization" | "cast-lock";

export function OnboardingFlow({ onStoryReady }: { onStoryReady: (storyId: string) => void }) {
  const [step, setStep] = useState<Step>("seed");
  const [seed, setSeed] = useState("");
  const [template, setTemplate] = useState<string | null>(null);

  return (
    <section className="mx-auto max-w-2xl rounded-xl border border-stone-700 bg-[#191724] p-8">
      <p className="font-mono text-xs uppercase tracking-[0.16em] text-teal-300">Start a story</p>
      <h1 className="mt-3 text-2xl font-semibold">
        {step === "seed" && "What do you want to write about?"}
        {step === "template" && "Pick a starting point"}
        {step === "personalization" && "Personalize (optional)"}
        {step === "cast-lock" && "Ready to begin"}
      </h1>

      <div className="mt-6">
        {step === "seed" && (
          <SeedForm
            onContinue={(value) => {
              setSeed(value);
              setStep("template");
            }}
          />
        )}
        {step === "template" && (
          <div className="space-y-4">
            <TemplatePicker selected={template} onSelect={setTemplate} />
            <button
              type="button"
              disabled={!template}
              onClick={() => setStep("personalization")}
              className="rounded-lg bg-amber-300 px-4 py-3 font-medium text-stone-950 disabled:opacity-40"
            >
              Continue
            </button>
          </div>
        )}
        {step === "personalization" && (
          <PersonalizationConsent onLocked={() => setStep("cast-lock")} />
        )}
        {step === "cast-lock" && <CastLock seed={seed} onLocked={onStoryReady} />}
      </div>
    </section>
  );
}
