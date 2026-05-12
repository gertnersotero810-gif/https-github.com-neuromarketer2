import React from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  BarChart,
  Bar,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import type { Widget } from '../../api/dashboard';

interface WidgetRendererProps {
  widget: Widget;
}

const COLORS = ['#6366f1', '#8b5cf6', '#10b981', '#ec4899', '#f59e0b'];

export const WidgetRenderer: React.FC<WidgetRendererProps> = ({ widget }) => {
  const { chart, dataKey, title } = widget;

  // Generate clean mock data driven by the dataKey
  const data = [
    { name: 'Пн', [dataKey]: 12 },
    { name: 'Вт', [dataKey]: 19 },
    { name: 'Ср', [dataKey]: 3 },
    { name: 'Чт', [dataKey]: 5 },
    { name: 'Пт', [dataKey]: 2 },
    { name: 'Сб', [dataKey]: 14 },
    { name: 'Вс', [dataKey]: 8 },
  ];

  // Common Tooltip component props for dark theme
  const customTooltipProps = {
    contentStyle: {
      backgroundColor: '#11111a',
      borderColor: 'rgba(255, 255, 255, 0.08)',
      borderRadius: '8px',
      color: '#ffffff',
      boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
      backdropFilter: 'blur(8px)',
    },
    itemStyle: { color: '#ffffff', fontSize: '12px' },
    labelStyle: { color: '#94a3b8', fontSize: '11px', fontWeight: 600 },
  };

  const renderChart = () => {
    switch (chart) {
      case 'line':
        return (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.04)" vertical={false} />
              <XAxis dataKey="name" stroke="#64748b" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
              <YAxis stroke="#64748b" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
              <Tooltip {...customTooltipProps} />
              <Line type="monotone" dataKey={dataKey} stroke="#6366f1" strokeWidth={2.5} dot={{ r: 0 }} activeDot={{ r: 5, strokeWidth: 0, fill: '#6366f1' }} />
            </LineChart>
          </ResponsiveContainer>
        );

      case 'bar':
        return (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.04)" vertical={false} />
              <XAxis dataKey="name" stroke="#64748b" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
              <YAxis stroke="#64748b" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
              <Tooltip {...customTooltipProps} />
              <Bar dataKey={dataKey} fill="#8b5cf6" radius={[4, 4, 0, 0]} maxBarSize={32} />
            </BarChart>
          </ResponsiveContainer>
        );

      case 'area':
        return (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
              <defs>
                <linearGradient id="colorAreaGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.04)" vertical={false} />
              <XAxis dataKey="name" stroke="#64748b" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
              <YAxis stroke="#64748b" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
              <Tooltip {...customTooltipProps} />
              <Area type="monotone" dataKey={dataKey} stroke="#6366f1" strokeWidth={2} fillOpacity={1} fill="url(#colorAreaGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        );

      case 'pie':
        const pieData = data.map((item) => ({
          name: item.name,
          value: item[dataKey],
        }));
        return (
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={38}
                outerRadius={56}
                paddingAngle={4}
                dataKey="value"
              >
                {pieData.map((_entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip {...customTooltipProps} />
            </PieChart>
          </ResponsiveContainer>
        );

      case 'number':
        const lastValue = data[data.length - 1][dataKey];
        return (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              height: '100%',
              paddingLeft: '0.25rem',
            }}
          >
            <div style={{ fontSize: '2.75rem', fontWeight: 800, color: '#ffffff', letterSpacing: '-0.03em', lineHeight: 1 }}>
              {typeof lastValue === 'number' ? lastValue.toLocaleString() : lastValue}
            </div>
            <div style={{ fontSize: '0.8125rem', color: '#64748b', marginTop: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
              <span style={{ color: '#10b981', fontWeight: 600 }}>↑ 14.2%</span> с начала недели
            </div>
          </div>
        );

      default:
        return <div style={{ color: '#64748b' }}>Неизвестный формат виджета</div>;
    }
  };

  return (
    <div
      data-testid={`widget-${chart}`}
      className="widget-card"
      style={{
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
        height: '100%',
        background: '#11111a',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '12px',
        boxSizing: 'border-box',
        padding: '1.25rem',
        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.25)',
      }}
    >
      <div
        style={{
          marginBottom: '1rem',
          fontWeight: 700,
          color: '#94a3b8',
          fontSize: '0.75rem',
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
        }}
      >
        {title}
      </div>
      <div style={{ flex: 1, minHeight: 0, width: '100%' }}>
        {renderChart()}
      </div>
    </div>
  );
};
