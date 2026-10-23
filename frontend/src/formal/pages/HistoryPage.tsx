import { useMemo, useState } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../api-client';
import { ColumnHeader } from '../components/ColumnHeader';
import { EmptyState, ErrorState, LoadingState, StatusBadge } from '../components/States';
import type { CaseList } from '../types';

const groups = [
  { key: 'continue', title: '可继续' }, { key: 'waiting', title: '待复检或待补充' },
  { key: 'completed', title: '已结束' },
] as const;

function CaseRows({ items, onOpen }: { items: CaseList['items']; onOpen: (id: string) => void }) {
  if (!items.length) return <p className="muted">暂无病例。</p>;
  return <div className="case-list">{items.map(item => <button type="button" className="case-row" key={item.id} onClick={() => onOpen(item.id)}><span><strong>{[item.vehicle.brand, item.vehicle.model, item.vehicle.engine_code].filter(Boolean).join(' · ')}</strong><small>{item.fault_description}</small><small>{item.fault_codes.join('、')}</small><small>{item.experience.guidance}</small>{Boolean(item.template_progress?.latest_repair) && <small>最近处理：{String(item.template_progress?.latest_repair)}</small>}{Boolean(item.template_progress?.latest_retest_outcome) && <small>最近复检：{({resolved:'原问题未再出现',persists:'原问题仍存在',uncertain:'结果尚不确定'} as Record<string,string>)[String(item.template_progress?.latest_retest_outcome)] ?? '已记录'}</small>}</span><span><StatusBadge value={item.experience.label} tone={item.experience.category === 'completed' ? 'good' : undefined} /><small>{new Date(item.updated_at).toLocaleString()}</small></span></button>)}</div>;
}

export function HistoryPage() {
  const [draft, setDraft] = useState('');
  const [scope, setScope] = useState<'daily' | 'test' | 'all'>('daily');
  const navigate = useNavigate();
  const query = useInfiniteQuery({
    queryKey: ['case-history', scope],
    initialPageParam: null as string | null,
    refetchOnMount: 'always',
    queryFn: ({ signal, pageParam }) => apiClient.request<CaseList>(`/cases?limit=50&scope=${scope}${pageParam !== null ? `&cursor=${encodeURIComponent(pageParam)}` : ''}`, { signal }),
    getNextPageParam: (lastPage, pages) => {
      const cursor = lastPage.next_cursor;
      if (cursor === null || pages.slice(0, -1).some(page => page.next_cursor === cursor)) return undefined;
      return cursor;
    },
  });
  const needle = draft.trim().toLowerCase();
  const allItems = useMemo(() => {
    const byId = new Map<string, CaseList['items'][number]>();
    query.data?.pages.forEach(page => page.items.forEach(item => { if (!byId.has(item.id)) byId.set(item.id, item); }));
    return [...byId.values()].sort((a, b) => a.experience.priority - b.experience.priority || b.updated_at.localeCompare(a.updated_at));
  }, [query.data]);
  const items = allItems.filter(item => [item.id, item.vehicle.model, item.vehicle.vin ?? '', item.fault_description, ...item.fault_codes].some(value => value.toLowerCase().includes(needle)));

  return <section className="page-card"><ColumnHeader eyebrow="HISTORY" title="继续或恢复病例" />
    <p className="section-note">查看病例记录；未结束的病例可以继续记录；已结束的病例打开后可选择“继续此病例”。</p>
    <div className="search-row" role="group" aria-label="病例范围">
      {([{ value: 'daily', label: '日常病例' }, { value: 'test', label: '测试与验证' }, { value: 'all', label: '全部病例' }] as const).map(option =>
        <button key={option.value} type="button" className={scope === option.value ? '' : 'secondary'} aria-pressed={scope === option.value} onClick={() => setScope(option.value)}>{option.label}</button>)}
    </div>
    <p className="muted">{scope === 'test' ? '按主诉开头的明确标签归类，原始记录完整保留。' : scope === 'daily' ? '找不到病例时，可切换到“全部病例”。' : '包含日常病例及带有测试、模拟或验收标签的病例。'}</p>
    <div className="search-row"><label>筛选病例、车型、VIN、故障码或描述<input value={draft} onChange={e => setDraft(e.target.value)} /></label></div>
    {query.isFetching && !query.isFetchingNextPage && !query.data && <LoadingState label="正在读取病例" />}
    {query.isFetchingNextPage && <LoadingState label="正在继续搜索后续病例" />}
    {query.error && <ErrorState error={query.error} onRetry={() => query.data ? query.fetchNextPage() : query.refetch()} />}
    {query.data && !items.length && !query.error && <EmptyState title="没有匹配病例">可切换病例范围、调整筛选条件，或从工作台建立新病例。</EmptyState>}
    {groups.map((group, index) => { const grouped = items.filter(item => item.experience.category === group.key); if (!grouped.length) return null; const content = <CaseRows items={grouped} onOpen={id => navigate(`/workbench/${id}`)} />; return index < 2 ? <section key={group.key}><h2>{group.title}</h2>{content}</section> : <details key={group.key}><summary>{group.title}（{grouped.length}）</summary>{content}</details>; })}
    {query.hasNextPage && <button type="button" className="secondary" disabled={query.isFetchingNextPage} onClick={() => query.fetchNextPage()}>{query.isFetchingNextPage ? '正在加载…' : '加载更早病例'}</button>}
  </section>;
}
