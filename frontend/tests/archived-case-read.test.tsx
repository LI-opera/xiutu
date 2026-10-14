import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { apiClient } from '../src/formal/api-client';
import { FormalCaseAnalysis } from '../src/formal/design/workbench-v2/FormalCaseAnalysis';
import { CurrentStep, EvidenceDrawer } from '../src/formal/diagnosis/ArchivedReadParts';
import type { StepCandidate } from '../src/formal/diagnosis/types';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it('shows a saved historical step without an observation action', () => {
  const candidate: StepCandidate = {
    type: 'propose_step', component_key: 'P01', title: '检查插头',
    purpose: { text: '检查连接状态' }, prerequisites: [],
    actions: [{ operation: 'inspect', text: '检查插头是否牢固' }],
    input: { kind: 'choice', choices: [{ text: '牢固' }] }, interpretation: [],
  };
  render(<CurrentStep candidate={candidate} onEvidence={() => undefined} />);
  expect(screen.getByText('检查插头是否牢固')).toBeTruthy();
  expect(screen.queryByRole('button', { name: /保存观察|提交|更正/ })).toBeNull();
});

it('opens the original location of a historical evidence version', async () => {
  vi.spyOn(apiClient, 'request').mockResolvedValue({
    evidence_id: 'evidence-old', synthetic: false,
    snapshot: { locator: { page: 7 }, sha256: 'old-version-hash' },
    current_validity: { valid: false, reasons: ['SOURCE_REVOKED'] },
    source_access: { kind: 'pdf', status: 'available', page: 7,
      content_url: '/api/v2/documents/doc/versions/version-old/content?page=7#page=7' },
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><EvidenceDrawer evidenceIds={['evidence-old']} onClose={() => undefined} /></QueryClientProvider>);
  expect(await screen.findByText('来源失效')).toBeTruthy();
  expect(screen.getByRole('link', { name: '打开原文与定位' }).getAttribute('href'))
    .toBe('/api/v2/documents/doc/versions/version-old/content?page=7#page=7');
});

it('reads historical case advice without offering the retired analysis request', async () => {
  const request = vi.spyOn(apiClient, 'request').mockResolvedValue({
    gate: { allowed: false, reason: '历史病例只读', missing_question_ids: [] },
    configuration: { mode: 'off', enabled: false }, items: [], preview: null,
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><FormalCaseAnalysis caseId="old-case" revision={1}
    onQuestion={vi.fn()} onAsset={vi.fn()} /></QueryClientProvider>);
  expect(await screen.findByText('准备状态：历史病例只读')).toBeTruthy();
  expect(request).toHaveBeenCalledWith('/cases/old-case/analyses', expect.objectContaining({ timeoutMs: 20_000 }));
  expect(screen.queryByRole('button', { name: /请求病例分析建议|重新请求分析/ })).toBeNull();
  expect(screen.queryByText('本次将发送的资料与预算')).toBeNull();
});
