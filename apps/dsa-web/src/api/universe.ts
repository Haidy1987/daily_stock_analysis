import apiClient from './index';

export type AShareUniverseItem = {
  code: string;
  name: string;
  exchange: string;
  canonical_code: string;
  board?: string | null;
  industry?: string | null;
  active: boolean;
};

export type AShareUniverseSearchResponse = {
  query: string;
  items: AShareUniverseItem[];
  total: number;
  offset: number;
  limit: number;
};

export type AShareUniverseStats = {
  total_count: number;
  total_including_inactive: number;
  sync_status: 'idle' | 'running' | 'cooldown' | string;
  cooldown_seconds: number;
  cooldown_remaining_seconds: number;
  next_available_at?: string | null;
  last_triggered_at?: string | null;
  last_completed_at?: string | null;
  last_success_at?: string | null;
  last_error?: string | null;
  last_report: Record<string, unknown>;
  manual_only: boolean;
  auto_sync_enabled: boolean;
};

export type AShareUniverseManualSyncResponse = {
  accepted: boolean;
  message: string;
  sync_status: string;
};

export const universeApi = {
  async search(params: { q?: string; limit?: number; offset?: number }): Promise<AShareUniverseSearchResponse> {
    const { data } = await apiClient.get<AShareUniverseSearchResponse>('/api/v1/universe/a-share/search', {
      params: {
        q: params.q ?? '',
        limit: params.limit ?? 50,
        offset: params.offset ?? 0,
      },
    });
    return data;
  },

  async getStats(): Promise<AShareUniverseStats> {
    const { data } = await apiClient.get<AShareUniverseStats>('/api/v1/universe/a-share/stats');
    return data;
  },

  async triggerManualSync(): Promise<AShareUniverseManualSyncResponse> {
    const { data } = await apiClient.post<AShareUniverseManualSyncResponse>('/api/v1/universe/a-share/sync');
    return data;
  },
};
