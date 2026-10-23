import { ApiError, errorText } from '../lib/api-client';

export function LoadingState({ label = '正在读取真实状态' }: { label?: string }) {
  return <div className="state loading" role="status"><span aria-hidden="true" />{label}…</div>;
}

export function EmptyState({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className="state empty-state"><strong>{title}</strong><p>{children}</p></div>;
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const trace = error instanceof ApiError ? error.traceId : null;
  const details = error instanceof ApiError ? error.details : null;
  return <div className="state error-state" role="alert"><strong>{errorText(error)}</strong>
    {trace && <div className="trace"><code>trace_id: {trace}</code><button type="button" className="text-button" onClick={() => navigator.clipboard.writeText(trace)}>复制</button></div>}
    {details && <details><summary>结构化详情</summary><pre>{JSON.stringify(details, null, 2)}</pre></details>}
    {onRetry && <button type="button" className="secondary" onClick={onRetry}>重试</button>}
  </div>;
}

export function StatusBadge({ value, tone = 'neutral' }: { value: string; tone?: 'neutral' | 'good' | 'warn' | 'bad' }) {
  return <span className={`status-badge ${tone}`}>{value}</span>;
}
