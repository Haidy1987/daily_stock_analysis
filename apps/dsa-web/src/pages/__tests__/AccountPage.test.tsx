import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AccountPage from '../AccountPage';

const { useAuthMock, useUiLanguageMock } = vi.hoisted(() => ({
  useAuthMock: vi.fn(),
  useUiLanguageMock: vi.fn(),
}));

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock('../../contexts/UiLanguageContext', () => ({
  useUiLanguage: () => useUiLanguageMock(),
}));

describe('AccountPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useUiLanguageMock.mockReturnValue({
      t: (key: string) => key,
    });
  });

  it('does not refresh global auth state again when entering the page', () => {
    const refreshStatus = vi.fn();
    useAuthMock.mockReturnValue({
      authEnabled: true,
      currentUser: { id: 1, username: 'admin', role: 'admin', status: 'active' },
      passwordChangeable: false,
      logoutAll: vi.fn(),
      refreshStatus,
    });

    render(<AccountPage />);

    expect(screen.getByText('admin')).toBeInTheDocument();
    expect(refreshStatus).not.toHaveBeenCalled();
  });
});
