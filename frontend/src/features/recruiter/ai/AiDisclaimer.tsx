import { Icon } from "../../../shared/components/Icon";

/** The human-in-the-loop notice every AI surface must carry (product
 * direction § 9) — a small, calm line, never a modal or blocking banner, so
 * it registers without getting in the way of using the tool. */
export function AiDisclaimer({ compact = false }: { compact?: boolean }) {
  return (
    <p className={`ai-disclaimer${compact ? " ai-disclaimer-compact" : ""}`}>
      <Icon name="shield" size={14} />
      AI-assisted recruitment insights are provided to support human review. Final hiring
      decisions are made by authorized personnel.
    </p>
  );
}
