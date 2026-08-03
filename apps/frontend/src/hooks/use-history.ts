import { useState, useEffect, useCallback } from 'preact/hooks';
import type { User } from '@supabase/supabase-js';
import { supabase } from '@/lib/supabase';
import type { Message } from '@/lib/chat';

export type ChatSession = {
  id: string;
  product_scope: string | null;
  created_at: string;
  /** First user message, used as the list item title. */
  title: string;
};

export function useHistory(user: User | null) {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!user) {
      setSessions([]);
      return;
    }
    setLoading(true);
    const { data } = await supabase
      .from('chat_sessions')
      .select('id, product_scope, created_at, chat_messages(role, content)')
      .order('created_at', { ascending: false })
      .limit(30);

    setSessions(
      (data ?? []).map((row) => {
        const msgs = (row.chat_messages as { role: string; content: string }[]) ?? [];
        const first = msgs.find((m) => m.role === 'user');
        return {
          id: row.id as string,
          product_scope: row.product_scope as string | null,
          created_at: row.created_at as string,
          title: first?.content?.slice(0, 60) ?? '—',
        };
      }),
    );
    setLoading(false);
  }, [user]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function loadMessages(sessionId: string): Promise<Message[]> {
    const { data } = await supabase
      .from('chat_messages')
      .select('role, content')
      .eq('session_id', sessionId)
      .order('created_at', { ascending: true })
      .limit(60);

    return (data ?? []).map((m) => ({
      role: m.role as Message['role'],
      content: m.content as string,
    }));
  }

  return { sessions, loading, refresh, loadMessages };
}
