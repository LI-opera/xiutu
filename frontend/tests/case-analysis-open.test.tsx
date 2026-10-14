import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { OpenGuidanceResult } from '../src/formal/design/workbench-v2/FormalCaseAnalysis';

afterEach(cleanup);

function sample() {
  return {
    id: 'analysis', mode: 'stub', provider: 'model_substitute', model: 'fixture',
    input_revision: 60, current_revision: 60, stale: false,
    content: {
      summary: '<script>window.bad=true</script> 接头异常',
      directions: [{ title: '可能连接松动', basis_observation_ids: ['fact', 'wrong-fact'],
                     counter_observation_ids: [], source_ids: ['source', 'wrong-source'] }],
      missing: [{ question_id: 'AIR-07', missing: '记录接头状态' },
                { question_id: 'UNKNOWN', missing: '错误问题引用' }],
      steps: [{ kind: 'repair', action: '模型撰写的维修建议', question_ids: ['UNKNOWN'],
                basis_observation_ids: [], source_ids: [] }],
      precautions: [],
    },
    basis: {
      observations: [{ id: 'fact', question_id: 'AIR-07', question: '接头状态', option_labels: ['未座合'] }],
      sources: [{ id: 'source', source_ref: 'manual', section: '接头', page: 2, text: '手册正文', asset_ids: [] }],
      questions: [{ id: 'AIR-07', title: '接头状态', answer_kind: 'single', target_question_id: 'AIR-07' }],
      images: [],
    },
  };
}

it('keeps bad references local, navigates only a known question, and renders text inertly', () => {
  const onQuestion = vi.fn();
  const { container } = render(<OpenGuidanceResult analysis={sample() as never} onQuestion={onQuestion} onAsset={vi.fn()} />);
  expect(screen.getAllByText('无法定位对应问题（UNKNOWN）')).toHaveLength(2);
  expect(container.querySelector('script')).toBeNull();
  expect(screen.getByText(/<script>window.bad=true<\/script>/)).toBeTruthy();
  fireEvent.click(screen.getAllByRole('button', { name: /前往接头状态/ })[0]);
  expect(onQuestion).toHaveBeenCalledWith('AIR-07');
  expect(onQuestion).toHaveBeenCalledTimes(1);
  expect(screen.getByText('建议步骤')).toBeTruthy();
  expect(screen.queryByRole('button', { name: /记录实际处理/ })).toBeNull();
  expect(screen.queryByRole('button', { name: '记录已实施的维修' })).toBeNull();
  fireEvent.click(screen.getAllByText('查看依据')[0]);
  expect(screen.getByText('观察引用未匹配（wrong-fact）')).toBeTruthy();
  expect(screen.getByText('资料引用未匹配（wrong-source）')).toBeTruthy();
});

it('shows v2 current advice separately from collapsed conditional options without saving facts', () => {
  const fixture = sample();
  fixture.content.steps = [{ kind: 'check', action: '定位检查', question_ids: ['AIR-07'],
    basis_observation_ids: ['fact'], source_ids: ['source'] }];
  const analysis = {
    ...fixture,
    content: { ...fixture.content, publication: { contract_version: 'case-advice-open-c19-v2' },
      conditional_branches: [{ trigger: '确认连接处泄漏', steps: [{ kind: 'repair', action: '按适用结构处理',
        question_ids: [], basis_observation_ids: ['fact'], source_ids: ['source'] }] }] },
  };
  const onQuestion = vi.fn();
  render(<OpenGuidanceResult analysis={analysis as never} onQuestion={onQuestion} onAsset={vi.fn()} />);
  expect(screen.getByRole('heading', { name: '当前建议' })).toBeTruthy();
  expect(screen.getByRole('heading', { name: '确认异常后的处理' })).toBeTruthy();
  expect(screen.getByText('定位检查')).toBeTruthy();
  const branch = screen.getByText('若发现：确认连接处泄漏').closest('details');
  expect(branch?.open).toBe(false);
  fireEvent.click(screen.getByText('若发现：确认连接处泄漏'));
  expect(branch?.open).toBe(true);
  expect(screen.getAllByText('建议步骤')).toHaveLength(2);
  expect(screen.queryByRole('button', { name: /记录实际处理/ })).toBeNull();
  expect(screen.queryByRole('button', { name: '记录已实施的维修' })).toBeNull();
  fireEvent.click(screen.getAllByRole('button', { name: /前往接头状态/ })[0]);
  expect(onQuestion).toHaveBeenCalledWith('AIR-07');
  fireEvent.click(screen.getAllByText('查看依据')[0]);
  expect(screen.getAllByText('手册正文').length).toBeGreaterThan(0);
});

it('does not duplicate the repair form entry inside a historical analysis', () => {
  render(<OpenGuidanceResult analysis={sample() as never} onQuestion={vi.fn()}
    onAsset={vi.fn()} />);
  expect(screen.queryByRole('button', { name: '记录已实施的维修' })).toBeNull();
  expect(screen.getByText('模型撰写的维修建议')).toBeTruthy();
});
