import { Link } from "react-router-dom";
import { LogoMark } from "../../shared/components/Icon";
import { ThemeToggle } from "../theme/ThemeToggle";

/** The slim top bar shared by every candidate-facing page (careers list, role
 * detail, campus drive, assessment): the organization's name beside the mark,
 * and the theme switch. Deliberately quiet — candidates are here to read and
 * apply, not to navigate. */
export function PublicHeader({ title }: { title: string }) {
  return (
    <header className="public-nav">
      <Link to="/" className="public-brand">
        <LogoMark size={26} />
        <span className="topbar-title">{title}</span>
      </Link>
      <ThemeToggle />
    </header>
  );
}
