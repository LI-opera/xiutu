import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { SynthesisGrid } from '../src/formal/design/workbench-v2/TemplateWorkbenchPage';

afterEach(cleanup);

it('links a template summary to the selected matched area and can show all matched areas', () => {
  const questionMap = new Map([
    ['AIR-01', { area_id: 'boost-air', title: '空气入口' }],
    ['AIR-02', { area_id: 'boost-air', title: '空气软管' }],
    ['PRS-01', { area_id: 'pressure', title: '压力信号' }],
    ['PRS-02', { area_id: 'pressure', title: '压力记录' }],
    ['PRS-03', { area_id: 'pressure', title: '压力缺项' }],
    ['IN-08', { area_id: null, title: '接诊安全' }],
  ]);
  const data = {
    topic: { areas: [{ id: 'boost-air', title: '增压空气通路' }, { id: 'pressure', title: '增压压力测量' }] },
    view: {
      synthesis: {
        facts: [{ question_id: 'AIR-01', option_ids: ['normal'] }, { question_id: 'PRS-01', option_ids: ['recorded'] }, { question_id: 'IN-08', option_ids: ['none'] }],
        issues: [{ question_id: 'AIR-02', option_ids: ['loose'] }, { question_id: 'PRS-02', option_ids: ['jumping'] }],
        unavailable: [], conflicts: [], missing_question_ids: ['PRS-03'], next_step: '',
      },
      areas: [], derived: {}, ai_readiness: { reasons: [] },
    },
  };
  const { rerender } = render(<SynthesisGrid data={data as never} label={(id) => id} questionMap={questionMap as never}
    templateBound selectedAreaId="pressure" />);

  expect(screen.getByText(/当前汇总全部匹配区域/)).toBeTruthy();
  expect(screen.getByRole('button', { name: /增压压力测量 · PRS-01/ })).toBeTruthy();
  expect(screen.getByRole('button', { name: /增压空气通路 · AIR-01/ })).toBeTruthy();
  expect(screen.queryByText('IN-08')).toBeNull();

  fireEvent.click(screen.getByRole('button', { name: '只看当前区域' }));
  expect(screen.getByText(/当前汇总“增压压力测量”/)).toBeTruthy();
  expect(screen.getByRole('button', { name: 'PRS-01' })).toBeTruthy();
  expect(screen.getByRole('button', { name: 'PRS-02' })).toBeTruthy();
  expect(screen.getByRole('button', { name: /压力缺项：尚未记录/ })).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'AIR-01' })).toBeNull();

  fireEvent.click(screen.getByRole('button', { name: '查看全部匹配区域' }));
  rerender(<SynthesisGrid data={data as never} label={(id) => id} questionMap={questionMap as never}
    templateBound selectedAreaId="boost-air" />);
  expect(screen.getByText(/当前汇总“增压空气通路”/)).toBeTruthy();
  expect(screen.getByRole('button', { name: 'AIR-01' })).toBeTruthy();
  expect(screen.getByRole('button', { name: 'AIR-02' })).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'PRS-01' })).toBeNull();
});
