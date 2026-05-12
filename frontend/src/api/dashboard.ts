import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';

export interface Widget {
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
  chart: 'line' | 'bar' | 'pie' | 'area' | 'number';
  dataKey: string;
  title: string;
  filters?: {
    campaign_id?: string;
    date_from?: string;
    date_to?: string;
  };
  data?: Record<string, any>[];
}

export interface DashboardResponse {
  widgets: Widget[];
}

// Optional: configure default baseURL if needed, but relative URLs are perfect for production under Nginx proxy
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
});

export const useGetDashboard = (projectId: string) => {
  return useQuery<DashboardResponse>({
    queryKey: ['dashboard', projectId],
    queryFn: async ({ signal }) => {
      const { data } = await apiClient.get(`/api/v1/projects/${projectId}/dashboard`, { signal });
      return data;
    },
    enabled: !!projectId,
  });
};

export const useSaveLayout = (projectId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { widgets: Widget[] }) => {
      const { data } = await apiClient.put(`/api/v1/projects/${projectId}/dashboard/layout`, payload);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard', projectId] });
    },
  });
};
