import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';

export default function MainLayout() {
  const location = useLocation();

  const getPageTitle = (pathname) => {
    switch (pathname) {
      case '/': return 'Security Overview & Telemetry';
      case '/datasets': return 'Network Flow Datasets';
      case '/models': return 'Model Lab & Evaluator';
      case '/predictions': return 'Inference & Prediction Workspace';
      case '/explainability': return 'Explainable AI (SHAP & Stability)';
      case '/audit': return 'Cryptographic Audit Ledger';
      case '/experiments': return 'Research Experiments (EXP-A to EXP-D)';
      case '/docs': return 'Architecture & Specification';
      case '/settings': return 'System Settings & Config';
      default: return 'SentinelCrypt AI';
    }
  };

  return (
    <div className="app-layout">
      <Sidebar />
      <div className="main-wrapper">
        <Header pageTitle={getPageTitle(location.pathname)} />
        <main className="page-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
