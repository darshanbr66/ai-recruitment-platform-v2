const STORAGE_KEY = "sigvi-teaser-dismissed";

// Session storage is a convenience only — it can be missing, full or blocked
// (private windows, embedded previews) and the teaser must work without it.
export function wasTeaserDismissed(): boolean {
  try {
    return window.sessionStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function rememberTeaserDismissed(): void {
  try {
    window.sessionStorage.setItem(STORAGE_KEY, "1");
  } catch {
    // ignore
  }
}
