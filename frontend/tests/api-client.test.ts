import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, apiClient, errorText } from '../src/lib/api-client';

afterEach(() => apiClient.clearSession());

describe('ApiClient', () => {
  it.each([
    [409, 'REVISION_CONFLICT', '当前数据已变化'],
    [413, 'UPLOAD_TOO_LARGE', '文件超过服务端'],
    [422, 'VALIDATION_ERROR', '输入不符合'],
  ])('preserves structured %s errors and maps readable text', async (status, code, text) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code, message: 'server detail', retryable: false, trace_id: '11111111-1111-4111-8111-111111111111', details: { field: 'x' } } }), { status, headers: { 'content-type': 'application/json' } })));
    const error = await apiClient.request('/x').catch(value => value as ApiError);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe(code);
    expect(error.details).toEqual({ field: 'x' });
    expect(errorText(error)).toContain(text);
  });

  it('sends CSRF, idempotency and JSON without persisting session data', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'content-type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);
    apiClient.setCsrf('csrf-value');
    await apiClient.request('/cases', { method: 'POST', body: { a: 1 }, idempotencyKey: 'case:key' });
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    const headers = init.headers as Headers;
    expect(headers.get('X-CSRF-Token')).toBe('csrf-value');
    expect(headers.get('Idempotency-Key')).toBe('case:key');
    expect(init.credentials).toBe('same-origin');
  });

  it('aborts a timed-out request', async () => {
    vi.stubGlobal('fetch', vi.fn((_url, init) => new Promise((_resolve, reject) => (init as RequestInit).signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError'))))));
    await expect(apiClient.request('/slow', { timeoutMs: 5 })).rejects.toMatchObject({ name: 'AbortError' });
  });

  it('notifies the session boundary when a later API call returns 401', async () => {
    const expired = vi.fn();
    window.addEventListener('xiutu:unauthorized', expired);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: 'AUTH_REQUIRED', message: 'expired', retryable: false, trace_id: null, details: null } }), { status: 401, headers: { 'content-type': 'application/json' } })));
    await expect(apiClient.request('/cases')).rejects.toMatchObject({ status: 401 });
    expect(expired).toHaveBeenCalledOnce();
    window.removeEventListener('xiutu:unauthorized', expired);
  });
});

it('recovers credentials without replaying a failed write, then uses the new CSRF on manual resubmit', async () => {
  const json=(data:unknown,status=200)=>new Response(JSON.stringify(data),{status,headers:{'content-type':'application/json'}});
  const fetchMock=vi.fn().mockResolvedValueOnce(json({error:{code:'AUTH_REQUIRED',message:'expired'}},401))
    .mockResolvedValueOnce(json({actor_id:'operator',csrf_token:'new-csrf',expires_in:3600}))
    .mockResolvedValueOnce(json({id:'case'}));
  vi.stubGlobal('fetch',fetchMock); apiClient.setCsrf('old-csrf');
  const body={fault_description:'保留的输入'};
  const error=await apiClient.request('/cases',{body,idempotencyKey:'same-attempt'}).catch(e=>e);
  expect(error.code).toBe('SESSION_RESTORED'); expect(errorText(error)).toContain('输入已保留');
  expect(fetchMock).toHaveBeenCalledTimes(2);
  expect(fetchMock.mock.calls[1][0]).toBe('/api/v2/auth/session');
  await apiClient.request('/cases',{body,idempotencyKey:'same-attempt'});
  const headers=fetchMock.mock.calls[2][1].headers as Headers;
  expect(headers.get('X-CSRF-Token')).toBe('new-csrf');
  expect(headers.get('Idempotency-Key')).toBe('same-attempt');
});

it('only recovers the specific stale CSRF failure, not arbitrary forbidden responses', async()=>{
  const response=(code:string)=>new Response(JSON.stringify({error:{code,message:code}}),{status:403});
  const fetchMock=vi.fn().mockResolvedValueOnce(response('CSRF_INVALID')).mockResolvedValueOnce(new Response(JSON.stringify({csrf_token:'fresh'})))
    .mockResolvedValueOnce(response('FORBIDDEN'));
  vi.stubGlobal('fetch',fetchMock);
  await expect(apiClient.request('/cases',{body:{}})).rejects.toMatchObject({code:'SESSION_RESTORED'});
  await expect(apiClient.request('/cases',{body:{}})).rejects.toMatchObject({code:'FORBIDDEN'});
  expect(fetchMock).toHaveBeenCalledTimes(3);
});
