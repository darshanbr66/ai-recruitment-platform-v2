import { Icon } from "../../shared/components/Icon";
import { SigviMascot } from "./SigviMascot";
import { SIGVI_CAPABILITIES, SIGVI_SUGGESTIONS } from "./suggestions";

/** The first thing a visitor sees when they open Sigvi. It goes away once the
 * conversation starts (a compact greeting takes its place). */
export function SigviWelcome({
  onPick,
  disabled,
}: {
  onPick: (question: string) => void;
  disabled: boolean;
}) {
  return (
    <section className="sigvi-welcome-hero" aria-label="Welcome">
      <div className="sigvi-hero-mascot">
        <SigviMascot
          size={90}
          variant="full"
          label="Sigvi, the SIGVITAS AI assistant — a friendly robot"
        />
      </div>
      <h3 className="sigvi-hero-title">
        Hi, I'm Sigvi <span aria-hidden="true">👋</span>
      </h3>
      <p className="sigvi-hero-sub">Your AI assistant for SIGVITAS.</p>

      <p className="sigvi-hero-lead">I can help you explore:</p>
      <ul className="sigvi-can">
        {SIGVI_CAPABILITIES.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>

      <div className="sigvi-suggest-grid" role="group" aria-label="Suggested questions">
        {SIGVI_SUGGESTIONS.map(({ label, icon }) => (
          <button
            key={label}
            type="button"
            className="sigvi-suggest"
            disabled={disabled}
            onClick={() => onPick(label)}
          >
            <span className="sigvi-suggest-icon" aria-hidden="true">
              <Icon name={icon} size={16} />
            </span>
            <span className="sigvi-suggest-label">{label}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
