import { NavLink, Outlet } from 'react-router-dom';
import { useSession } from '../lib/session';

export function AppShell() {
  const { logout } = useSession();
  return <div className="formal-app">
    <header className="app-header">
      <NavLink to="/workbench" className="formal-brand" aria-label="修途工作台首页"><b>修途</b><span>Evidence-led diagnostics</span></NavLink>
      <nav aria-label="正式应用导航">
        <NavLink to="/workbench">工作台</NavLink>
        <NavLink to="/documents" end>维修资料</NavLink>
        <NavLink to="/history">历史病例</NavLink>
      </nav>
      <div className="header-actions"><button type="button" className="text-button" onClick={logout}>退出</button></div>
    </header>
    <main className="app-main"><Outlet /></main>
  </div>;
}
