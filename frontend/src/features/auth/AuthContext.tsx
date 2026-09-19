import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { ApiError } from "../../lib/apiClient";
import type { TokenResponse, UserResponse } from "../../types/auth";
import {
  fetchCurrentUser,
  login as loginRequest,
  logout as logoutRequest,
  refreshSession,
} from "./api";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  status: AuthStatus;
  user: UserResponse | null;
  accessToken: string | null;
  isSuperAdmin: boolean;
  login: (email: string, password: string) => Promise<UserResponse>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/** Renew this long before the access token expires. */
const RENEWAL_LEEWAY_MS = 60_000;
const MIN_RENEWAL_DELAY_MS = 5_000;
/** A failed renewal that wasn't a definitive "session is over" is retried. */
const RENEWAL_RETRY_MS = 30_000;
/** Page-load restore: the API may be cold-starting (e.g. a sleeping Render
 * instance answers with a 5xx or drops the connection for a while). */
const BOOTSTRAP_RETRY_DELAYS_MS = [2_000, 4_000, 8_000, 16_000];

let inflightRefresh: Promise<TokenResponse> | null = null;

/**
 * Every refresh call rotates the refresh-token cookie, and the backend
 * treats presenting an already-rotated token as theft and revokes the whole
 * token family (docs/architecture.md § 4). Two overlapping refreshes — React
 * StrictMode runs the mount effect twice in development, and the renewal
 * timer can coincide with a tab becoming visible — would therefore log the
 * user out. All callers share one in-flight request instead.
 */
function refreshSessionOnce(): Promise<TokenResponse> {
  if (inflightRefresh === null) {
    inflightRefresh = refreshSession().finally(() => {
      inflightRefresh = null;
    });
  }
  return inflightRefresh;
}

/** A 401 from the refresh endpoint is the server saying there is no valid
 * session. Anything else (network drop, 5xx) says nothing about the session
 * and must not sign the user out. */
function isSessionEnded(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Holds the access token in memory only (never localStorage) — the refresh
 * token lives in an httpOnly cookie the browser manages, per
 * docs/architecture.md § 4. On mount, a silent refresh restores the session
 * after a page reload without ever putting the access token in storage a
 * script could read; afterwards the token is renewed shortly before it
 * expires so a long-lived tab never ends up holding an expired token.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<UserResponse | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);

  const renewalTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const expiresAt = useRef(0);
  // `scheduleRenewal` and `renew` call each other; the ref breaks the cycle.
  const renewRef = useRef<() => Promise<void>>(async () => {});

  const clearRenewalTimer = useCallback(() => {
    if (renewalTimer.current !== null) {
      clearTimeout(renewalTimer.current);
      renewalTimer.current = null;
    }
  }, []);

  const scheduleRenewal = useCallback(
    (expiresInSeconds: number) => {
      clearRenewalTimer();
      expiresAt.current = Date.now() + expiresInSeconds * 1000;
      const wait = Math.max(expiresInSeconds * 1000 - RENEWAL_LEEWAY_MS, MIN_RENEWAL_DELAY_MS);
      renewalTimer.current = setTimeout(() => void renewRef.current(), wait);
    },
    [clearRenewalTimer],
  );

  const endSession = useCallback(() => {
    clearRenewalTimer();
    setAccessToken(null);
    setUser(null);
    setStatus("unauthenticated");
  }, [clearRenewalTimer]);

  const renew = useCallback(async () => {
    try {
      const tokens = await refreshSessionOnce();
      setAccessToken(tokens.access_token);
      scheduleRenewal(tokens.expires_in);
    } catch (error) {
      if (isSessionEnded(error)) {
        endSession();
        return;
      }
      clearRenewalTimer();
      renewalTimer.current = setTimeout(() => void renewRef.current(), RENEWAL_RETRY_MS);
    }
  }, [clearRenewalTimer, endSession, scheduleRenewal]);

  useEffect(() => {
    renewRef.current = renew;
  }, [renew]);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      for (let attempt = 0; ; attempt++) {
        try {
          const tokens = await refreshSessionOnce();
          const currentUser = await fetchCurrentUser(tokens.access_token);
          if (cancelled) return;
          setAccessToken(tokens.access_token);
          setUser(currentUser);
          setStatus("authenticated");
          scheduleRenewal(tokens.expires_in);
          return;
        } catch (error) {
          if (cancelled) return;
          const retryDelay = BOOTSTRAP_RETRY_DELAYS_MS[attempt];
          if (isSessionEnded(error) || retryDelay === undefined) {
            setStatus("unauthenticated");
            return;
          }
          await delay(retryDelay);
          if (cancelled) return;
        }
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [scheduleRenewal]);

  // Timers are throttled or suspended while a tab is hidden or the machine
  // sleeps, so the scheduled renewal can fire late — catch up on return.
  useEffect(() => {
    if (status !== "authenticated") return;
    function handleVisibilityChange() {
      if (
        document.visibilityState === "visible" &&
        expiresAt.current - Date.now() < RENEWAL_LEEWAY_MS
      ) {
        void renewRef.current();
      }
    }
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => document.removeEventListener("visibilitychange", handleVisibilityChange);
  }, [status]);

  useEffect(() => clearRenewalTimer, [clearRenewalTimer]);

  const login = useCallback(
    async (email: string, password: string) => {
      const tokens = await loginRequest(email, password);
      const currentUser = await fetchCurrentUser(tokens.access_token);
      setAccessToken(tokens.access_token);
      setUser(currentUser);
      setStatus("authenticated");
      scheduleRenewal(tokens.expires_in);
      return currentUser;
    },
    [scheduleRenewal],
  );

  const logout = useCallback(async () => {
    try {
      await logoutRequest();
    } catch {
      // Best-effort: still clear local state even if the network call fails.
    }
    endSession();
  }, [endSession]);

  const value = useMemo(
    () => ({
      status,
      user,
      accessToken,
      isSuperAdmin: user?.organization_id === null && status === "authenticated",
      login,
      logout,
    }),
    [status, user, accessToken, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth must be used within an AuthProvider.");
  }
  return context;
}
