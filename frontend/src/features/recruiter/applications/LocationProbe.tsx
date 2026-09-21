import { useLocation } from "react-router-dom";

/** Test-only: renders the current router location so tests can assert what is in the URL. */
export function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname + location.search}</output>;
}
