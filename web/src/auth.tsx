import { useCallback, useContext, useEffect, useState, createContext, type ReactNode } from "react";
import { api, getStoredUser, getToken, storeSession, type User } from "./api";

interface AuthCtx {
  user: User | null;
  ready: boolean;
  login: (username: string, passcode: string) => Promise<void>;
  switchUser: (username: string) => Promise<User>;
  logout: () => void;
}
const Ctx = createContext<AuthCtx>(null!);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => (getToken() ? getStoredUser() : null));
  const [ready, setReady] = useState(() => !!(getToken() && getStoredUser()));

  const enterPublic = useCallback(async () => {
    const r = await api<{ access_token: string; user: User }>("/auth/public", { method: "POST" });
    storeSession(r.access_token, r.user);
    setUser(r.user);
    setReady(true);
  }, []);

  useEffect(() => {
    const onLogout = () => { void enterPublic(); };
    window.addEventListener("hmt:logout", onLogout);
    if (!getToken() || !getStoredUser()) void enterPublic();
    return () => window.removeEventListener("hmt:logout", onLogout);
  }, [enterPublic]);

  const login = async (username: string, passcode: string) => {
    const r = await api<{ access_token: string; user: User }>("/auth/login", { body: { username, passcode } });
    storeSession(r.access_token, r.user);
    setUser(r.user);
    setReady(true);
  };
  const switchUser = async (username: string) => {
    const r = await api<{ access_token: string; user: User }>("/auth/demo-switch", { body: { username } });
    storeSession(r.access_token, r.user);
    setUser(r.user);
    setReady(true);
    return r.user;
  };
  const logout = () => { storeSession(null, null); setUser(null); void enterPublic(); };
  return <Ctx.Provider value={{ user, ready, login, switchUser, logout }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
export const isCrewWide = (u: User | null) => !!u && u.role !== "astronaut";
