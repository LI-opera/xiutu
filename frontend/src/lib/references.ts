import type { ReferenceItem, StoredVehicle } from './types';

export const REFERENCE_ID = /^[a-z0-9][a-z0-9-]{1,99}$/;
export const MAX_REFERENCE_CHARS = 2_000_000;

export const statusLabel: Record<string, string> = {
  queued: '排队中', processing: '处理中', ready: '可用', failed: '失败',
};

export const statusTone = (status: string): 'neutral' | 'good' | 'warn' | 'bad' =>
  status === 'ready' ? 'good' : status === 'failed' ? 'bad' : status === 'queued' || status === 'processing' ? 'warn' : 'neutral';

export const isWorking = (status: string) => status === 'queued' || status === 'processing';

/** A document ID from a file name; Chinese-only names get a short random suffix. */
export function referenceIdFrom(fileName: string, random = () => Math.random().toString(16).slice(2, 8)) {
  const base = fileName.replace(/\.[^.]+$/, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 90);
  return base.length >= 2 ? base : `doc-${random()}`;
}

/** The `## ` headings of a Markdown text: the unit an always-included section is chosen by. */
export function sectionHeadings(text: string) {
  return text.replace(/\r\n?/g, '\n').split('\n').filter(line => /^## +\S/.test(line)).map(line => line.trim());
}

export type ReferenceGroup = { documentId: string; title: string; versions: ReferenceItem[] };

/** Versions grouped by document, newest version first; documents in list order. */
export function groupReferences(items: ReferenceItem[]): ReferenceGroup[] {
  const groups = new Map<string, ReferenceGroup>();
  for (const item of items) {
    const group = groups.get(item.document_id) ?? { documentId: item.document_id, title: item.title, versions: [] };
    group.versions.push(item);
    groups.set(item.document_id, group);
  }
  return [...groups.values()].map(group => {
    const versions = [...group.versions].sort((a, b) => Number(b.version) - Number(a.version) || b.created_at.localeCompare(a.created_at));
    return { ...group, title: versions[0].title, versions };
  });
}

/** "大众 探岳 2019 DKVB"; unknown parts are left out. */
export const vehicleText = (vehicle: StoredVehicle) =>
  [vehicle.brand, vehicle.model, vehicle.year, vehicle.engine_code].filter(v => v !== null && v !== '').join(' ') || '未填写';

/** Distinct values of one vehicle field, for typing suggestions. */
export const suggestions = (vehicles: StoredVehicle[], field: keyof StoredVehicle) =>
  [...new Set(vehicles.map(v => v[field]).filter((v): v is string | number => v !== null && v !== '').map(String))].sort();
