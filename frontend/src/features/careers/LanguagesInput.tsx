import { useId, useState, type KeyboardEvent } from "react";
import { Icon } from "../../shared/components/Icon";

/** Suggestions only — any language can be typed. The backend validates and
 * normalizes every entry (app/schemas/candidate.py::normalize_languages). */
const COMMON_LANGUAGES = [
  "English",
  "Hindi",
  "Tamil",
  "Telugu",
  "Kannada",
  "Malayalam",
  "Marathi",
  "Bengali",
  "Gujarati",
  "Punjabi",
  "Urdu",
  "Odia",
  "French",
  "German",
  "Spanish",
  "Arabic",
  "Japanese",
  "Mandarin",
];

const MAX_LANGUAGES = 15;

export function LanguagesInput({
  value,
  onChange,
  disabled,
}: {
  value: string[];
  onChange: (next: string[]) => void;
  disabled?: boolean;
}) {
  const [draft, setDraft] = useState("");
  const inputId = useId();
  const listId = useId();

  function add(raw: string) {
    const name = raw.trim().replace(/\s+/g, " ");
    if (!name) return;
    if (value.some((existing) => existing.toLowerCase() === name.toLowerCase())) {
      setDraft("");
      return;
    }
    if (value.length >= MAX_LANGUAGES) return;
    onChange([...value, name]);
    setDraft("");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      add(draft);
    } else if (event.key === "Backspace" && draft === "" && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  }

  return (
    <div className="field">
      <label htmlFor={inputId}>
        Languages known <span className="required-mark" aria-hidden="true">*</span>
      </label>
      {value.length > 0 && (
        <ul className="language-chips" aria-label="Languages added">
          {value.map((language) => (
            <li key={language} className="chip">
              {language}
              <button
                type="button"
                className="chip-remove"
                onClick={() => onChange(value.filter((item) => item !== language))}
                disabled={disabled}
                aria-label={`Remove ${language}`}
              >
                <Icon name="x" size={12} />
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="language-entry">
        <input
          id={inputId}
          list={listId}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={() => add(draft)}
          placeholder={value.length === 0 ? "e.g. English" : "Add another language"}
          disabled={disabled}
          aria-describedby={`${inputId}-hint`}
          aria-required="true"
        />
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={() => add(draft)}
          disabled={disabled || !draft.trim()}
        >
          Add
        </button>
      </div>
      <datalist id={listId}>
        {COMMON_LANGUAGES.filter((language) => !value.includes(language)).map((language) => (
          <option key={language} value={language} />
        ))}
      </datalist>
      <span id={`${inputId}-hint`} className="field-hint">
        Press Enter after each language.
      </span>
    </div>
  );
}
