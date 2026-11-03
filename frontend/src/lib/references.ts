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

export const PACKAGE_SCHEMA = 'xiutu-guide-package/1';
export const PACKAGE_FILES = ['manifest.json', 'guide.md', 'sources.json'] as const;

export type GuidePackage = {
  manifest: Record<string, unknown>; guide: string; sources: string;
  documentId: string; title: string; vehicle: string; reviewer: string | null; approved: boolean;
  alwaysInclude: string[]; openGaps: number; packageVersion: string;
};

/**
 * The three files of a guide package (picked together), read as written: the server checks
 * their hashes, so nothing is normalized here. Returns the package or the problems found.
 */
export function readPackage(files: { name: string; text: string }[]): { pkg: GuidePackage | null; problems: string[] } {
  const byName = new Map(files.map(f => [f.name.split(/[\\/]/).pop() ?? f.name, f.text]));
  const missing = PACKAGE_FILES.filter(name => !byName.has(name));
  if (missing.length) return { pkg: null, problems: [`缺少文件：${missing.join('、')}（请同时选中资料包文件夹里的三个文件）`] };
  let manifest: Record<string, unknown>;
  try { manifest = JSON.parse(byName.get('manifest.json') ?? ''); } catch { return { pkg: null, problems: ['manifest.json 不是有效的 JSON'] }; }
  if (manifest.schema_version !== PACKAGE_SCHEMA) return { pkg: null, problems: [`manifest.json 不是 ${PACKAGE_SCHEMA} 格式的资料包`] };
  const review = (manifest.review ?? {}) as { status?: string; reviewer?: string | null };
  const applicability = ((manifest.applicability ?? []) as Record<string, unknown>[])[0] ?? {};
  const pkg: GuidePackage = {
    manifest, guide: byName.get('guide.md') ?? '', sources: byName.get('sources.json') ?? '',
    documentId: String(manifest.document_id ?? ''), title: String(manifest.title ?? ''),
    vehicle: [applicability.brand, applicability.model, applicability.year_from, applicability.engine_code].filter(Boolean).join(' '),
    reviewer: review.reviewer ?? null, approved: review.status === 'approved',
    alwaysInclude: (manifest.always_include ?? []) as string[],
    openGaps: ((manifest.open_gaps ?? []) as unknown[]).length, packageVersion: String(manifest.version ?? ''),
  };
  const problems = pkg.approved ? [] : ['资料包还没有通过人工审核：审核后在 xiutu-clean 运行 approve.py 标为已通过，再导入'];
  return { pkg, problems };
}
