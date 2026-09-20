import { avatarStyle, initials } from "../lib/avatar";

/** Initials in a soft tile; decorative (the name is always rendered beside it). */
export function Avatar({ name, large = false }: { name: string | null | undefined; large?: boolean }) {
  return (
    <span className={`avatar${large ? " avatar-lg" : ""}`} style={avatarStyle(name)} aria-hidden="true">
      {initials(name)}
    </span>
  );
}
