import apiClient from './index';

export type AdminUserSummary = {
  id: number;
  username: string;
  email?: string | null;
  role: 'admin' | 'user' | string;
  status: 'active' | 'disabled' | string;
  createdAt?: string | null;
  updatedAt?: string | null;
  lastLoginAt?: string | null;
};

export type AdminUserListResponse = {
  items: AdminUserSummary[];
  total: number;
  page: number;
  pageSize: number;
};

export type CreateAdminUserRequest = {
  username: string;
  password: string;
  role?: 'admin' | 'user';
  email?: string | null;
};

export type UpdateAdminUserRequest = {
  role?: 'admin' | 'user';
  status?: 'active' | 'disabled';
  email?: string | null;
};

export const adminUsersApi = {
  async list(params?: {
    page?: number;
    pageSize?: number;
    search?: string;
    role?: string;
    status?: string;
  }): Promise<AdminUserListResponse> {
    const { data } = await apiClient.get<AdminUserListResponse>('/api/v1/admin/users', {
      params: {
        page: params?.page,
        pageSize: params?.pageSize,
        search: params?.search || undefined,
        role: params?.role || undefined,
        status: params?.status || undefined,
      },
    });
    return data;
  },

  async create(body: CreateAdminUserRequest): Promise<AdminUserSummary> {
    const { data } = await apiClient.post<AdminUserSummary>('/api/v1/admin/users', body);
    return data;
  },

  async update(userId: number, body: UpdateAdminUserRequest): Promise<AdminUserSummary> {
    const { data } = await apiClient.patch<AdminUserSummary>(`/api/v1/admin/users/${userId}`, body);
    return data;
  },

  async disable(userId: number): Promise<void> {
    await apiClient.delete(`/api/v1/admin/users/${userId}`);
  },

  async resetPassword(userId: number, newPassword: string): Promise<void> {
    await apiClient.post(`/api/v1/admin/users/${userId}/reset-password`, {
      newPassword,
    });
  },

  async revokeSessions(userId: number): Promise<void> {
    await apiClient.post(`/api/v1/admin/users/${userId}/revoke-sessions`);
  },
};
