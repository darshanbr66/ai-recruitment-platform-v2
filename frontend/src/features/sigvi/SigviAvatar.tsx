import { SigviMascot, type MascotState } from "./SigviMascot";

/** The still, decorative mascot head that sits beside each assistant message
 * (and the header). The full animated mascot is `SigviMascot`. */
export function SigviAvatar({
  size = 32,
  state = "idle",
  animated = false,
}: {
  size?: number;
  state?: MascotState;
  animated?: boolean;
}) {
  return <SigviMascot size={size} variant="head" state={state} animated={animated} />;
}
