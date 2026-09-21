"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import type { Session } from "@supabase/supabase-js";
import { getSupabase } from "@/lib/supabase";

type Membership = {
  workspace_id: string;
  role: string;
  workspaces: { name: string } | null;
};
type Auth = {
  demo: boolean;
  ready: boolean;
  configured: boolean;
  session: Session | null;
  memberships: Membership[];
  workspace: string;
  role: string;
  selectWorkspace: (id: string) => void;
  error: string;
};
const Context = createContext<Auth>({
  demo: false,
  ready: false,
  configured: false,
  session: null,
  memberships: [],
  workspace: "",
  role: "",
  selectWorkspace: () => {},
  error: "",
});
export const useAuth = () => useContext(Context);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [demoWorkspace, setDemoWorkspace] = useState("");
  const [session, setSession] = useState<Session | null>(null);
  const [memberships, setMemberships] = useState<Membership[]>([]);
  const [workspace, setWorkspace] = useState("");
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [configured, setConfigured] = useState(false);
  useEffect(() => {
    setDemoWorkspace(sessionStorage.getItem("draftwise-demo-workspace") || "");
    const supabase = getSupabase();
    setConfigured(Boolean(supabase));
    if (!supabase) {
      setReady(true);
      return;
    }
    const { data: listener } = supabase.auth.onAuthStateChange(
      (_event, nextSession) => {
        setSession(nextSession);
      },
    );
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setReady(true);
    }).catch(() => { setError("Could not restore your session. Please sign in again."); setReady(true); });
    return () => listener.subscription.unsubscribe();
  }, []);
  useEffect(() => {
    if (!session) {
      setMemberships([]);
      setWorkspace("");
      return;
    }
    let cancelled = false;
    getSupabase()!
      .from("memberships")
      .select("workspace_id,role,workspaces(name)")
      .eq("user_id", session.user.id)
      .then(({ data, error }) => {
        if (cancelled) return;
        if (error) {
          setError("We could not load your workspaces. Please refresh.");
          return;
        }
        const rows = (data || []) as unknown as Membership[];
        setMemberships(rows);
        const saved = localStorage.getItem("shipping-workspace");
        const selected =
          rows.find((row) => row.workspace_id === saved)?.workspace_id ||
          rows[0]?.workspace_id ||
          "";
        setWorkspace(selected);
        if (selected) localStorage.setItem("shipping-workspace", selected);
      });
    return () => {
      cancelled = true;
    };
  }, [session]);
  function selectWorkspace(id: string) {
    if (!memberships.some((row) => row.workspace_id === id)) return;
    localStorage.setItem("shipping-workspace", id);
    setWorkspace(id);
  }
  return (
    <Context.Provider
      value={{
        ready,
        demo: Boolean(demoWorkspace),
        configured,
        session,
        memberships,
        workspace: demoWorkspace || workspace,
        role: demoWorkspace
          ? "admin"
          : memberships.find((row) => row.workspace_id === workspace)?.role ||
            "",
        selectWorkspace,
        error: demoWorkspace ? "" : error,
      }}
    >
      {children}
    </Context.Provider>
  );
}
