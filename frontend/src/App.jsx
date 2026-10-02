import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import MainLayout from './components/layout/MainLayout';

// Pages
import Dashboard from './pages/Dashboard';
import Datasets from './pages/Datasets';
import Models from './pages/Models';
import Predictions from './pages/Predictions';
import Explainability from './pages/Explainability';
import AuditLedger from './pages/AuditLedger';
import Experiments from './pages/Experiments';
import ProfessorMode from './pages/ProfessorMode';
import Documentation from './pages/Documentation';
import Settings from './pages/Settings';
import Benchmark from './pages/Benchmark';
import Challenges from './pages/Challenges';
import Provenance from './pages/Provenance';
import Review from './pages/Review';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="datasets" element={<Datasets />} />
          <Route path="models" element={<Models />} />
          <Route path="predictions" element={<Predictions />} />
          <Route path="explainability" element={<Explainability />} />
          <Route path="audit" element={<AuditLedger />} />
          <Route path="experiments" element={<Experiments />} />
          <Route path="benchmark" element={<Benchmark />} />
          <Route path="challenges" element={<Challenges />} />
          <Route path="provenance" element={<Provenance />} />
          <Route path="review" element={<Review />} />
          <Route path="professor-mode" element={<ProfessorMode />} />
          <Route path="docs" element={<Documentation />} />
          <Route path="settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
