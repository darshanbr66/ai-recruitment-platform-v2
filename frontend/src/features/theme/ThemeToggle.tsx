import { Icon } from "../../shared/components/Icon";
import { useTheme } from "./ThemeContext";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const label = theme === "dark" ? "Switch to light mode" : "Switch to dark mode";

  return (
    <button type="button" className="theme-toggle" onClick={toggleTheme} aria-label={label} title={label}>
      {/* keyed so the icon swaps with a small turn, the only motion here */}
      <span key={theme} className="theme-toggle-icon">
        <Icon name={theme === "dark" ? "sun" : "moon"} size={18} />
      </span>
    </button>
  );
}
