import type { ReactNode } from 'react';

export function ColumnHeader({ eyebrow, title, action }: { eyebrow: string; title: string; action?: ReactNode }) {
  return <div className="column-header"><div><span>{eyebrow}</span><h2>{title}</h2></div>{action}</div>;
}
