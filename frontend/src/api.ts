import type { AuthSession } from './api-schema';
let csrf = '';
export class ApiError extends Error {
    constructor(public status: number, public code: string, message: string) { super(message); }
}
export function setSession(s: AuthSession | null) { csrf = s?.csrf_token ?? ''; }
export async function api<T>(path: string, body?: unknown, method = body === undefined ? 'GET' : 'POST', idempotencyKey?: string): Promise<T> {
    const headers: Record<string, string> = {};
    if (method !== 'GET') {
        headers['X-CSRF-Token'] = csrf;
        headers['Idempotency-Key'] = idempotencyKey ?? crypto.randomUUID();
    }
    if (body !== undefined && !(body instanceof FormData))
        headers['Content-Type'] = 'application/json';
    const r = await fetch('/api/v2' + path, { method, headers, credentials: 'same-origin', body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body) });
    if (!r.ok) {
        let e;
        try {
            e = await r.json();
        }
        catch {
            e = {};
        }
        ;
        throw new ApiError(r.status, e.error?.code ?? 'HTTP_ERROR', e.error?.message ?? `HTTP ${r.status}`);
    }
    return r.json() as Promise<T>;
}
export async function source(path: string) { const r = await fetch(path, { credentials: 'same-origin' }); if (!r.ok)
    throw new ApiError(r.status, 'SOURCE_UNAVAILABLE', '原文暂不可读取'); return r; }
