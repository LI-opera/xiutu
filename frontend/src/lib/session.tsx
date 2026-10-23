import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient, ApiError } from './api-client';
import type { AuthSession } from './types';
import { ErrorState, LoadingState } from '../components/States';

type SessionContextValue = { session: AuthSession; logout: () => void };
const SessionContext = createContext<SessionContextValue | null>(null);

export function useSession() {
  const value = useContext(SessionContext);
  if (!value) throw new Error('SessionProvider missing');
  return value;
}

function Login() {
  const [token, setToken] = useState('');
  const client = useQueryClient();
  const login = useMutation({
    mutationFn: () => apiClient.request<AuthSession>('/auth/login', { method: 'POST', body: { token: token.trim().replace(/^`|`$/g, '') } }),
    onSuccess: session => { apiClient.setCsrf(session.csrf_token); setToken(''); client.setQueryData(['session'], session); },
  });
  return <main className="login-page"><section className="login-panel"><p className="kicker">LOCAL OPERATOR SESSION</p><h1>连接修途工作台</h1><p>访问令牌只用于建立 HttpOnly cookie 会话，不会写入浏览器存储。</p>
    <label>访问令牌<input aria-label="访问令牌" type="password" autoComplete="off" value={token} onChange={e => setToken(e.target.value)} /></label>
    <button type="button" disabled={login.isPending || token.trim().replace(/^`|`$/g, '').length < 32} onClick={() => login.mutate()}>进入正式应用</button>
    {login.error && <ErrorState error={login.error} />}
  </section></main>;
}

export function SessionBoundary({ children }: { children: React.ReactNode }) {
  const client = useQueryClient();
  const query = useQuery<AuthSession | null>({ queryKey: ['session'], queryFn: () => apiClient.request<AuthSession>('/auth/session'), retry: false });
  useEffect(() => { if (query.data) apiClient.setCsrf(query.data.csrf_token); }, [query.data]);
  useEffect(() => {
    const expire = () => {
      apiClient.clearSession();
      void client.invalidateQueries({ queryKey: ['session'] });
    };
    const restored = (event: Event) => client.setQueryData(['session'], (event as CustomEvent<AuthSession>).detail);
    window.addEventListener('xiutu:unauthorized', expire);
    window.addEventListener('xiutu:session-restored', restored);
    return () => {
      window.removeEventListener('xiutu:unauthorized', expire);
      window.removeEventListener('xiutu:session-restored', restored);
    };
  }, [client]);
  const logoutMutation = useMutation({
    mutationFn: () => apiClient.request('/auth/logout', { method: 'POST', body: {} }),
    onSettled: () => { apiClient.clearSession(); client.clear(); void query.refetch(); },
  });
  const value = useMemo(() => query.data ? { session: query.data, logout: () => logoutMutation.mutate() } : null, [query.data, logoutMutation]);
  if (query.isPending) return <div className="formal-app"><LoadingState label="正在恢复会话" /></div>;
  // Preserve mounted drafts while a previously authenticated session is recovered.
  if (value) return <SessionContext.Provider value={value}>
    <div hidden={Boolean(query.error)} inert={Boolean(query.error)}>{children}</div>
    {query.error && (query.error instanceof ApiError && query.error.status === 401
      ? <Login /> : <main className="login-page"><ErrorState error={query.error} onRetry={() => query.refetch()} /></main>)}
  </SessionContext.Provider>;
  if (query.error instanceof ApiError && query.error.status === 401) return <Login />;
  if (query.error) return <main className="login-page"><ErrorState error={query.error} onRetry={() => query.refetch()} /></main>;
  return value ? <SessionContext.Provider value={value}>{children}</SessionContext.Provider> : <Login />;
}
