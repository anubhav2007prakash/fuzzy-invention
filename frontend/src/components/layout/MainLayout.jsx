import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';

export default function MainLayout() {
  const location = useLocation();

  const getPageInfo = (pathname) => {
    switch (pathname) {
      case '/': return { title: 'Security Overview', section: 'Workspace' };
      case '/datasets': return { title: 'Network Flow Datasets', section: 'Core Pipelines' };
      case '/models': return { title: 'Model Lab & Evaluator', section: 'Core Pipelines' };
      case '/predictions': return { title: 'Inference Workspace', section: 'Workspace' };
      case '/explainability': return { title: 'SHAP Attribution & Stability', section: 'Core Pipelines' };
      case '/audit': return { title: 'Cryptographic Audit Ledger', section: 'Core Pipelines' };
      case '/experiments': return { title: 'Research Experiments (EXP A-D)', section: 'Research Suite' };
      case '/docs': return { title: 'Architecture Documentation', section: 'Research Suite' };
      case '/settings': return { title: 'System Environment & Config', section: 'Research Suite' };
      default: return { title: 'SentinelCrypt AI', section: 'Workspace' };
    }
  };

  const pageInfo = getPageInfo(location.pathname);

  return (
    <div className="app-layout">
      {/* Qronos Blueprint Framing Rails */}
      <div className="qronos-rails" aria-hidden="true">
        <div className="qronos-rail-left">
          <span className="qronos-crosshair" style={{ top: '10px', left: '-5px' }}>+</span>
          <span className="qronos-crosshair" style={{ bottom: '20px', left: '-5px' }}>+</span>
        </div>
        <div className="qronos-rail-right">
          <span className="qronos-crosshair" style={{ top: '10px', right: '-5px' }}>+</span>
          <span className="qronos-crosshair" style={{ bottom: '20px', right: '-5px' }}>+</span>
        </div>
      </div>

      <Sidebar />
      <div className="main-wrapper">
        <Header pageTitle={pageInfo.title} pageSection={pageInfo.section} />
        <main className="page-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
