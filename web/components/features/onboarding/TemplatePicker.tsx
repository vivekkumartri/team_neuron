"use client";

/**
 * Every option carries an explicit, visible disclosure label. Licensed
 * templates are clearly marked as such — nothing here is presented as
 * "original" unless it is.
 */
export interface TemplateOption {
  id: string;
  title: string;
  disclosure: "ORIGINAL" | "LICENSED_REFERENCE";
  description: string;
}

const TEMPLATES: TemplateOption[] = [
  {
    id: "original-custom",
    title: "Your own concept",
    disclosure: "ORIGINAL",
    description: "Start from your seed with no reference material.",
  },
  {
    id: "original-mystery",
    title: "Coastal mystery",
    disclosure: "ORIGINAL",
    description: "An original template built for slow-burn investigation arcs.",
  },
  {
    id: "licensed-noir",
    title: "Noir detective (licensed reference)",
    disclosure: "LICENSED_REFERENCE",
    description: "Pacing and tone inspired by public-domain noir fiction, clearly labeled.",
  },
];

export function TemplatePicker({
  selected,
  onSelect,
}: {
  selected: string | null;
  onSelect: (templateId: string) => void;
}) {
  return (
    <fieldset className="space-y-3">
      <legend className="text-sm font-medium text-stone-200">Choose a starting point</legend>
      {TEMPLATES.map((template) => (
        <label
          key={template.id}
          className={`flex cursor-pointer flex-col rounded-lg border p-4 ${
            selected === template.id ? "border-teal-300 bg-teal-950/20" : "border-stone-700"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="font-medium">{template.title}</span>
            <span
              className={`rounded-full px-2 py-0.5 text-xs ${
                template.disclosure === "LICENSED_REFERENCE"
                  ? "border border-amber-300 text-amber-200"
                  : "border border-teal-300 text-teal-200"
              }`}
            >
              {template.disclosure === "LICENSED_REFERENCE" ? "Licensed reference" : "Original"}
            </span>
          </div>
          <p className="mt-1 text-sm text-stone-300">{template.description}</p>
          <input
            type="radio"
            name="template"
            className="sr-only"
            checked={selected === template.id}
            onChange={() => onSelect(template.id)}
          />
        </label>
      ))}
    </fieldset>
  );
}
