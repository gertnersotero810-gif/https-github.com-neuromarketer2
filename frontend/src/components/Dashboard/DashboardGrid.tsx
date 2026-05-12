import React, { useEffect, useState } from 'react';
import { Responsive, WidthProvider } from 'react-grid-layout';
import axios from 'axios';
import { useGetDashboard, useSaveLayout } from '../../api/dashboard';
import { WidgetRenderer } from './WidgetRenderer';

import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

const ResponsiveGridLayout = WidthProvider(Responsive);

interface DashboardGridProps {
  projectId: string;
}

export const DashboardGrid: React.FC<DashboardGridProps> = ({ projectId }) => {
  const { data, isLoading, error } = useGetDashboard(projectId);
  const saveLayoutMutation = useSaveLayout(projectId);
  const [projectTitle, setProjectTitle] = useState<string>('');

  // 1. AbortController pattern from ARCHITECTURE.md section 3.1
  useEffect(() => {
    const controller = new AbortController();

    const fetchProjectDetails = async () => {
      try {
        const response = await axios.get(`/api/v1/projects/${projectId}`, {
          signal: controller.signal,
        });
        if (response.data && response.data.name) {
          setProjectTitle(response.data.name);
        }
      } catch (err) {
        if (axios.isCancel(err)) {
          // Silent handling on expected unmount cleanup to avoid noisy logs in console/vitest
          return;
        } else {
          console.error('Error fetching project details:', err);
        }
      }
    };

    if (projectId) {
      fetchProjectDetails();
    }

    return () => {
      controller.abort();
    };
  }, [projectId]);

  if (isLoading) {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: '20px', width: '100%', boxSizing: 'border-box' }}>
        {[1, 2, 3].map((id, index) => (
          <div
            key={id}
            className="animate-pulse"
            style={{
              gridColumn: index === 0 ? 'span 6' : index === 1 ? 'span 6' : 'span 12',
              height: index === 2 ? '300px' : '260px',
              background: '#11111a',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '12px',
              padding: '1.25rem',
              display: 'flex',
              flexDirection: 'column',
              boxSizing: 'border-box',
            }}
          >
            <div style={{ width: '35%', height: '12px', background: 'rgba(255,255,255,0.08)', borderRadius: '4px', marginBottom: '1.5rem' }} />
            <div style={{ flex: 1, background: 'rgba(255,255,255,0.03)', borderRadius: '8px' }} />
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          padding: '3rem 2rem',
          textAlign: 'center',
          background: 'rgba(239, 68, 68, 0.03)',
          borderRadius: '12px',
          border: '1px solid rgba(239, 68, 68, 0.12)',
          color: '#ef4444',
          maxWidth: '500px',
          margin: '3rem auto',
          boxSizing: 'border-box',
        }}
      >
        <div style={{ fontSize: '2rem', marginBottom: '0.75rem' }}>⚠️</div>
        <div style={{ fontSize: '1rem', fontWeight: 600, color: '#fca5a5' }}>
          Не удалось загрузить дашборд
        </div>
        <div style={{ fontSize: '0.875rem', marginTop: '0.5rem', color: '#fca5a5', opacity: 0.75 }}>
          {error.message}
        </div>
      </div>
    );
  }

  const widgets = data?.widgets || [];

  if (widgets.length === 0) {
    return (
      <div
        style={{
          padding: '5rem 2rem',
          textAlign: 'center',
          background: '#11111a',
          borderRadius: '12px',
          border: '1px dashed rgba(255, 255, 255, 0.1)',
          color: '#94a3b8',
          maxWidth: '600px',
          margin: '4rem auto',
          boxSizing: 'border-box',
        }}
      >
        <div style={{ fontSize: '3rem', marginBottom: '1.25rem', filter: 'grayscale(0.5)' }}>📊</div>
        <h3 style={{ fontSize: '1.125rem', fontWeight: 700, marginBottom: '0.5rem', color: '#ffffff', letterSpacing: '-0.01em' }}>
          Панель аналитики пуста
        </h3>
        <p style={{ fontSize: '0.875rem', color: '#64748b', maxWidth: '340px', margin: '0 auto', lineHeight: 1.5 }}>
          В этом проекте пока нет настроенных виджетов. Попробуйте выполнить импорт файлов или сохранить новый макет.
        </p>
      </div>
    );
  }

  // Construct layouts object required by react-grid-layout
  const layoutItems = widgets.map((w) => ({
    i: w.i,
    x: w.x,
    y: w.y,
    w: w.w,
    h: w.h,
    minW: 2,
    minH: 2,
  }));

  const layouts = {
    lg: layoutItems,
    md: layoutItems,
    sm: layoutItems,
  };

  const handleLayoutChange = (_currentLayout: any[], allLayouts: any) => {
    // We can use lg or current active layouts
    const activeLayout = allLayouts.lg || allLayouts.md || _currentLayout;
    
    // Check if anything actually changed to prevent infinite loops
    let hasChanged = false;

    const updatedWidgets = widgets.map((w) => {
      const item = activeLayout.find((l: any) => l.i === w.i);
      if (item) {
        if (item.x !== w.x || item.y !== w.y || item.w !== w.w || item.h !== w.h) {
          hasChanged = true;
          return {
            ...w,
            x: item.x,
            y: item.y,
            w: item.w,
            h: item.h,
          };
        }
      }
      return w;
    });

    if (hasChanged) {
      saveLayoutMutation.mutate({ widgets: updatedWidgets });
    }
  };

  return (
    <div style={{ width: '100%', boxSizing: 'border-box' }}>
      {projectTitle && (
        <div
          style={{
            marginBottom: '1.5rem',
            fontSize: '1rem',
            fontWeight: 600,
            color: '#818cf8',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <span style={{ width: '4px', height: '14px', background: '#6366f1', borderRadius: '2px' }} />
          Проект: {projectTitle}
        </div>
      )}
      <ResponsiveGridLayout
        className="layout"
        layouts={layouts}
        breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
        cols={{ lg: 12, md: 10, sm: 6, xs: 4, xxs: 2 }}
        rowHeight={100}
        onLayoutChange={handleLayoutChange}
        isDraggable={true}
        isResizable={true}
        margin={[20, 20]} // Premium slightly larger gap
      >
        {widgets.map((w) => (
          <div key={w.i}>
            <WidgetRenderer widget={w} />
          </div>
        ))}
      </ResponsiveGridLayout>
    </div>
  );
};
