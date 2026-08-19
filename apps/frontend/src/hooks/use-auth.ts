import { useState, useEffect } from 'preact/hooks';
import type { User } from '@supabase/supabase-js';
import { supabase } from '@/lib/supabase';

export type AuthState = {
  user: User | null;
  loading: boolean;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  /**
   * Current access token, or null when signed out.
   *
   * Read fresh from Supabase at call time rather than held in state: tokens
   * are refreshed in the background, and a copy captured at sign-in would go
   * stale mid-session and start failing writes with a 401 that looks like a
   * permissions problem.
   */
  getAccessToken: () => Promise<string | null>;
};

export function useAuth(): AuthState {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // No Supabase configured: settle immediately as signed-out. Leaving
    // `loading` true would hang the header on a state that can never resolve.
    if (!supabase) {
      setLoading(false);
      return;
    }

    supabase.auth.getSession().then(({ data }) => {
      setUser(data.session?.user ?? null);
      setLoading(false);
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
    });

    return () => listener.subscription.unsubscribe();
  }, []);

  async function login() {
    if (!supabase) return;
    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin },
    });
  }

  async function logout() {
    if (!supabase) return;
    await supabase.auth.signOut();
  }

  async function getAccessToken(): Promise<string | null> {
    if (!supabase) return null;
    const { data } = await supabase.auth.getSession();
    return data.session?.access_token ?? null;
  }

  return { user, loading, login, logout, getAccessToken };
}
