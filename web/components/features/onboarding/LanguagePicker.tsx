"use client";

/**
 * Story-content and voice language, chosen once at story creation (task.md
 * Phase 6 multilingual entry) — this is NOT a UI i18n picker, the app's own
 * buttons/labels/forms stay English regardless of this choice. Only the
 * three languages this app supports for generated content and voice are
 * offered, matching `StoryLanguage` in `domain/models.py`. Each option shows
 * the language's own script for its label (not just the English name),
 * mirroring how a real multilingual product would present the choice.
 */
export type StoryLanguageCode = "en" | "hi" | "te";

export interface LanguageOption {
  code: StoryLanguageCode;
  label: string;
  englishName: string;
}

const LANGUAGES: LanguageOption[] = [
  { code: "en", label: "English", englishName: "English" },
  { code: "hi", label: "हिन्दी", englishName: "Hindi" },
  { code: "te", label: "తెలుగు", englishName: "Telugu" },
];

export function LanguagePicker({
  selected,
  onSelect,
}: {
  selected: StoryLanguageCode | null;
  onSelect: (language: StoryLanguageCode) => void;
}) {
  return (
    <fieldset className="space-y-3">
      <legend className="text-sm font-medium text-stone-200">
        Choose the story's language
      </legend>
      <p className="text-xs text-stone-400">
        Chapters, dialogue, and voice will use this language. The app's own
        controls stay in English.
      </p>
      <div className="grid grid-cols-3 gap-3">
        {LANGUAGES.map((language) => (
          <label
            key={language.code}
            className={`flex cursor-pointer flex-col items-center rounded-lg border p-4 text-center ${
              selected === language.code
                ? "border-teal-300 bg-teal-950/20"
                : "border-stone-700"
            }`}
          >
            <span className="text-lg font-medium">{language.label}</span>
            {language.code !== "en" && (
              <span className="mt-1 text-xs text-stone-400">{language.englishName}</span>
            )}
            <input
              type="radio"
              name="story-language"
              className="sr-only"
              checked={selected === language.code}
              onChange={() => onSelect(language.code)}
            />
          </label>
        ))}
      </div>
    </fieldset>
  );
}
