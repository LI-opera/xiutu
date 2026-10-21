import { useQuery } from '@tanstack/react-query';
import { useParams, useSearchParams } from 'react-router-dom';
import { apiClient } from '../api-client';
import { ErrorState, LoadingState } from '../components/States';
import type { CaseSnapshot } from '../types';
import { TemplateWorkbenchPage } from '../design/workbench-v2/TemplateWorkbenchPage';
import { LegacyDemoWorkbenchPage } from '../design/workbench-v2/LegacyDemoWorkbenchPage';
import { FormalWorkbenchV2IntakePage } from '../design/workbench-v2/FormalVehicleProfile';
import { formalTopicIdentity } from '../design/workbench-v2/topicIdentity';
import { RegionalCaseWorkbench } from './RegionalCaseWorkbench';

function FormalCaseRoute({ caseId }: { caseId: string }) {
  const [params] = useSearchParams();
  const snapshot = useQuery({ queryKey: ['case', caseId], queryFn: ({ signal }) => apiClient.request<CaseSnapshot>(`/cases/${caseId}`, { signal }) });
  if (snapshot.isPending) return <LoadingState label="正在确认病例工作台版本" />;
  if (snapshot.error || !snapshot.data) return <ErrorState error={snapshot.error ?? new Error('病例不存在')} onRetry={() => snapshot.refetch()} />;
  const binding = (snapshot.data.intake_snapshot as { topic_binding?: { topic_id?: string; version?: string; content_hash?: string } } | undefined)?.topic_binding;
  if ((snapshot.data.intake_snapshot as { workbench_flow?: string } | undefined)?.workbench_flow === 'template-match-v1') {
    return <TemplateWorkbenchPage key={caseId} caseId={caseId} />;
  }
  if (binding?.topic_id === 'tanyue-dkvb-p0299-demo-v2' && ['2.2.0-b01', '2.2.1-b02'].includes(binding.version ?? '')) {
    return <TemplateWorkbenchPage key={caseId} caseId={caseId} />;
  }
  const vehicle = snapshot.data.vehicle;
  const eligible = snapshot.data.diagnosis_mode === 'conservative' &&
    binding?.topic_id === formalTopicIdentity.topicId && binding.version === formalTopicIdentity.version && binding.content_hash === formalTopicIdentity.contentHash &&
    vehicle.model === '虚拟探岳 DKVB 演示台架' && vehicle.year === 2020 &&
    vehicle.engine_family === 'EA888 Gen3B DEMO' && vehicle.engine_code === 'DKVB-DEMO' &&
    snapshot.data.fault_codes.includes('P0299');
  // Browser-verified synthetic DKVB path only; ?legacy=1 remains the explicit rollback.
  return eligible && params.get('legacy') !== '1' ? <LegacyDemoWorkbenchPage caseId={caseId} /> : <RegionalCaseWorkbench caseId={caseId} />;
}

export function WorkbenchPage() { const { caseId } = useParams(); return caseId ? <FormalCaseRoute caseId={caseId} /> : <FormalWorkbenchV2IntakePage />; }
