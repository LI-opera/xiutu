import type { AuthSession, ErrorEnvelope } from './types';

type RequestOptions = {
  method?: 'GET' | 'POST';
  body?: unknown | FormData;
  idempotencyKey?: string;
  signal?: AbortSignal;
  timeoutMs?: number;
  response?: 'json' | 'text' | 'blob';
};

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly traceId: string | null,
    public readonly details: Record<string, unknown> | null,
    public readonly retryable: boolean,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export const idempotencyKey = (scope: string) =>
  `${scope}:${crypto.randomUUID()}`.slice(0, 128);

export function errorText(error: unknown): string {
  if (!(error instanceof ApiError)) {
    if (error instanceof DOMException && error.name === 'AbortError') return '请求已取消或超时。';
    return error instanceof Error ? error.message : '发生未知错误。';
  }
  if (error.code === 'SESSION_RESTORED') return '登录已恢复，输入已保留，请再次提交。';
  const defaults: Record<number, string> = {
    401: '登录已失效，请重新登录。',
    409: '当前数据已变化，请刷新后重试。',
    413: '文件超过服务端实际允许的大小。原资料不会被替换。',
    422: '输入不符合服务端约束，请检查字段。',
  };
  return `${defaults[error.status] ?? error.message}${error.message ? `（${error.message}）` : ''}`;
}

class ApiClient {
  private csrf = '';
  private recovery: Promise<AuthSession> | null = null;

  private recoverSession() {
    if (!this.recovery) {
      this.recovery = this.request<AuthSession>('/auth/session').then(session => {
        this.setCsrf(session.csrf_token);
        window.dispatchEvent(new CustomEvent('xiutu:session-restored', { detail: session }));
        return session;
      }).finally(() => { this.recovery = null; });
    }
    return this.recovery;
  }

  setCsrf(value: string) {
    this.csrf = value;
  }

  clearSession() {
    this.csrf = '';
  }

  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const method = options.method ?? (options.body === undefined ? 'GET' : 'POST');
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), options.timeoutMs ?? 15_000);
    const onAbort = () => controller.abort();
    options.signal?.addEventListener('abort', onAbort, { once: true });
    try {
      const headers = new Headers({ Accept: 'application/json' });
      let body: BodyInit | undefined;
      if (options.body instanceof FormData) body = options.body;
      else if (options.body !== undefined) {
        headers.set('Content-Type', 'application/json');
        body = JSON.stringify(options.body);
      }
      if (method !== 'GET') {
        if (this.csrf) headers.set('X-CSRF-Token', this.csrf);
        if (options.idempotencyKey) headers.set('Idempotency-Key', options.idempotencyKey);
      }
      const response = await fetch(`/api/v2${path}`, {
        method,
        headers,
        body,
        credentials: 'same-origin',
        signal: controller.signal,
      });
      if (!response.ok) {
        let payload: ErrorEnvelope | null = null;
        try { payload = await response.json() as ErrorEnvelope; } catch { /* non-JSON proxy error */ }
        const item = payload?.error;
        if (!path.startsWith('/auth/') && (response.status === 401 || (response.status === 403 && item?.code === 'CSRF_INVALID'))) {
          let restored = false;
          try { await this.recoverSession(); restored = true; }
          catch { window.dispatchEvent(new Event('xiutu:unauthorized')); }
          // Do not replay writes, model requests or timed-out submissions.
          if (restored) throw new ApiError(response.status, 'SESSION_RESTORED', '登录已恢复，输入已保留，请再次提交。', item?.trace_id ?? null, null, true);
        }
        throw new ApiError(
          response.status,
          item?.code ?? `HTTP_${response.status}`,
          item?.message ?? response.statusText,
          item?.trace_id ?? response.headers.get('x-trace-id'),
          (item?.details as Record<string, unknown> | null | undefined) ?? null,
          item?.retryable ?? false,
        );
      }
      if (options.response === 'text') return await response.text() as T;
      if (options.response === 'blob') return await response.blob() as T;
      if (response.status === 204) return undefined as T;
      return await response.json() as T;
    } finally {
      window.clearTimeout(timeout);
      options.signal?.removeEventListener('abort', onAbort);
    }
  }
}

export const apiClient = new ApiClient();
