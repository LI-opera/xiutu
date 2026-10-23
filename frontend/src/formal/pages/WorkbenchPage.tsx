import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { apiClient } from '../api-client';
import { EmptyState, ErrorState, LoadingState } from '../components/States';
import type { CaseSnapshot } from '../types';
import { TemplateWorkbenchPage } from '../design/workbench-v2/TemplateWorkbenchPage';
import { MatchedVehicleIntake } from '../design/workbench-v2/MatchedVehicleIntake';

function CaseRoute({ caseId }: { caseId: string }) {
  const snapshot = useQuery({ queryKey: ['case', caseId], queryFn: ({ signal }) => apiClient.request<CaseSnapshot>(`/cases/${caseId}`, { signal }) });
  if (snapshot.isPending) return <LoadingState label="正在读取病例" />;
  if (snapshot.error || !snapshot.data) return <ErrorState error={snapshot.error ?? new Error('病例不存在')} onRetry={() => snapshot.refetch()} />;
  if ((snapshot.data.intake_snapshot as { workbench_flow?: string } | undefined)?.workbench_flow !== 'template-match-v1') {
    return <EmptyState title="无法打开此病例">此病例不是模板病例，当前工作台不再支持。</EmptyState>;
  }
  return <TemplateWorkbenchPage key={caseId} caseId={caseId} />;
}

export function WorkbenchPage() { const { caseId } = useParams(); return caseId ? <CaseRoute caseId={caseId} /> : <MatchedVehicleIntake />; }
