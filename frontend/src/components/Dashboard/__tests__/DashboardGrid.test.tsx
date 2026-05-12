import { render, screen } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { DashboardGrid } from '../DashboardGrid';
import axios from 'axios';
import * as dashboardApi from '../../../api/dashboard';

// Mock the API hooks
vi.mock('../../../api/dashboard', () => ({
  useGetDashboard: vi.fn(),
  useSaveLayout: vi.fn(),
}));

// Mock ResizeObserver for jsdom
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Mock ResponsiveContainer from recharts to render its children directly
vi.mock('recharts', async () => {
  const original = await vi.importActual('recharts') as any;
  return {
    ...original,
    ResponsiveContainer: ({ children }: any) => (
      <div style={{ width: '100%', height: '100%', minWidth: '100px', minHeight: '100px' }}>
        {children}
      </div>
    ),
  };
});

describe('DashboardGrid Component Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(axios, 'get').mockResolvedValue({ data: { name: 'Тестовый Проект' } });
  });

  it('widget with chart:"line" renders widget-line', async () => {
    vi.mocked(dashboardApi.useGetDashboard).mockReturnValue({
      data: {
        widgets: [
          {
            i: 'line-widget',
            x: 0,
            y: 0,
            w: 6,
            h: 4,
            chart: 'line',
            dataKey: 'ctr',
            title: 'Line Chart KPI',
          },
        ],
      },
      isLoading: false,
      error: null,
    } as any);

    vi.mocked(dashboardApi.useSaveLayout).mockReturnValue({
      mutate: vi.fn(),
    } as any);

    render(<DashboardGrid projectId="test-uuid" />);

    expect(await screen.findByText('Проект: Тестовый Проект')).toBeInTheDocument();
    expect(screen.getByTestId('widget-line')).toBeInTheDocument();
    expect(screen.getByText('Line Chart KPI')).toBeInTheDocument();
  });

  it('widget with chart:"bar" renders widget-bar', async () => {
    vi.mocked(dashboardApi.useGetDashboard).mockReturnValue({
      data: {
        widgets: [
          {
            i: 'bar-widget',
            x: 0,
            y: 0,
            w: 6,
            h: 4,
            chart: 'bar',
            dataKey: 'spend',
            title: 'Spend Bar Chart',
          },
        ],
      },
      isLoading: false,
      error: null,
    } as any);

    vi.mocked(dashboardApi.useSaveLayout).mockReturnValue({
      mutate: vi.fn(),
    } as any);

    render(<DashboardGrid projectId="test-uuid" />);

    expect(await screen.findByText('Проект: Тестовый Проект')).toBeInTheDocument();
    expect(screen.getByTestId('widget-bar')).toBeInTheDocument();
    expect(screen.getByText('Spend Bar Chart')).toBeInTheDocument();
  });

  it('renders "Нет данных" empty state when widget has empty or missing data', async () => {
    vi.mocked(dashboardApi.useGetDashboard).mockReturnValue({
      data: {
        widgets: [
          {
            i: 'line-widget',
            x: 0,
            y: 0,
            w: 6,
            h: 4,
            chart: 'line',
            dataKey: 'ctr',
            title: 'Empty Line Chart',
            data: [], // empty data array
          },
        ],
      },
      isLoading: false,
      error: null,
    } as any);

    vi.mocked(dashboardApi.useSaveLayout).mockReturnValue({
      mutate: vi.fn(),
    } as any);

    render(<DashboardGrid projectId="test-uuid" />);

    expect(await screen.findByText('Проект: Тестовый Проект')).toBeInTheDocument();
    expect(screen.getByText('Нет данных для отображения')).toBeInTheDocument();
  });
});

