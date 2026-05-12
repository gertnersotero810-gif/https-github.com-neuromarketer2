import React from 'react';
import { DashboardGrid } from '../components/Dashboard/DashboardGrid';

interface ProjectDashboardProps {
  projectId?: string;
}

export const ProjectDashboard: React.FC<ProjectDashboardProps> = ({ projectId }) => {
  // Use passed projectId or fall back to a dummy UUID if none is supplied
  const resolvedProjectId = projectId || '00000000-0000-0000-0000-000000000000';

  return (
    <div
      style={{
        width: '100%',
        minHeight: '100vh',
        background: '#0a0a0f',
        backgroundImage: 'radial-gradient(circle at 50% -20%, rgba(99, 102, 241, 0.08), transparent 70%)',
        padding: '2rem',
        boxSizing: 'border-box',
        color: '#ffffff',
        fontFamily: 'system-ui, -apple-system, sans-serif',
      }}
    >
      <header
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          paddingBottom: '1.5rem',
          marginBottom: '2rem',
        }}
      >
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#ffffff', margin: 0, letterSpacing: '-0.02em' }}>
            Аналитический Дашборд
          </h1>
          <p style={{ fontSize: '0.875rem', color: '#64748b', margin: '0.375rem 0 0 0' }}>
            Обзор ключевых показателей эффективности кампаний
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.5rem',
              background: 'rgba(99, 102, 241, 0.1)',
              color: '#a5b4fc',
              fontSize: '0.75rem',
              fontWeight: 600,
              padding: '0.375rem 0.75rem',
              borderRadius: '9999px',
              border: '1px solid rgba(99, 102, 241, 0.2)',
            }}
          >
            <span
              style={{
                width: '6px',
                height: '6px',
                background: '#818cf8',
                borderRadius: '50%',
                display: 'inline-block',
                boxShadow: '0 0 8px #818cf8',
              }}
            />
            Режим реального времени
          </span>
        </div>
      </header>

      <main style={{ width: '100%' }}>
        <DashboardGrid projectId={resolvedProjectId} />
      </main>
    </div>
  );
};
