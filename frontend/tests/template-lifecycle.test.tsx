import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TemplateCaseLifecycle } from '../src/workbench/TemplateCaseLifecycle';
import { apiClient } from '../src/lib/api-client';
afterEach(cleanup);
it('closes only after explicit confirmation and reopens the same case', async()=>{
 const request=vi.spyOn(apiClient,'request').mockResolvedValue({});
 const onChanged=vi.fn(); const client=new QueryClient();
 const view=(closed:boolean)=><QueryClientProvider client={client}><TemplateCaseLifecycle caseId="original" revision={5} closed={closed} onChanged={onChanged}/></QueryClientProvider>;
 const ui=render(view(false));
 fireEvent.click(screen.getByText('结束本次工作')); expect(request).not.toHaveBeenCalled();
 fireEvent.click(screen.getByText('确认结束'));
 await waitFor(()=>expect(onChanged).toHaveBeenCalledOnce());
 expect(request).toHaveBeenLastCalledWith('/cases/original/template-lifecycle',expect.objectContaining({body:{expected_revision:5,closed:true}}));
 ui.rerender(view(true)); fireEvent.click(screen.getByText('继续此病例'));
 await waitFor(()=>expect(onChanged).toHaveBeenCalledTimes(2));
 expect(request).toHaveBeenLastCalledWith('/cases/original/template-lifecycle',expect.objectContaining({body:{expected_revision:5,closed:false}}));
});
