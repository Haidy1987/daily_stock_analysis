import type React from 'react';
import { useCallback, useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import {
  adminUsersApi,
  type AdminUserSummary,
  type CreateAdminUserRequest,
} from '../api/adminUsers';
import type { ParsedApiError } from '../api/error';
import { createParsedApiError, getParsedApiError } from '../api/error';
import {
  ApiErrorAlert,
  AppPage,
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  InlineAlert,
  Input,
  Loading,
  PageHeader,
  Pagination,
  Select,
} from '../components/common';
import { useAuth } from '../contexts/AuthContext';
import { useUiLanguage } from '../contexts/UiLanguageContext';

const PAGE_SIZE = 20;

type PendingAction =
  | { type: 'disable'; user: AdminUserSummary }
  | { type: 'enable'; user: AdminUserSummary }
  | { type: 'role'; user: AdminUserSummary; role: 'admin' | 'user' }
  | { type: 'reset'; user: AdminUserSummary; password: string }
  | { type: 'revoke'; user: AdminUserSummary }
  | null;

const AdminUsersPage: React.FC = () => {
  const { t } = useUiLanguage();
  const { authEnabled, currentUser, isLoading: authLoading } = useAuth();

  const [items, setItems] = useState<AdminUserSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingAction>(null);

  const [createUsername, setCreateUsername] = useState('');
  const [createPassword, setCreatePassword] = useState('');
  const [createRole, setCreateRole] = useState<'user' | 'admin'>('user');
  const [createdOnceHint, setCreatedOnceHint] = useState<string | null>(null);

  const [resetTarget, setResetTarget] = useState<AdminUserSummary | null>(null);
  const [resetPassword, setResetPassword] = useState('');
  const [resetPasswordConfirm, setResetPasswordConfirm] = useState('');

  useEffect(() => {
    document.title = t('adminUsers.pageTitle');
  }, [t]);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await adminUsersApi.list({
        page,
        pageSize: PAGE_SIZE,
        search: search || undefined,
        role: roleFilter || undefined,
        status: statusFilter || undefined,
      });
      setItems(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(getParsedApiError(err));
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, search, roleFilter, statusFilter]);

  useEffect(() => {
    if (authEnabled && currentUser?.role === 'admin') {
      void loadUsers();
    }
  }, [authEnabled, currentUser?.role, loadUsers]);

  if (authLoading) {
    return (
      <AppPage>
        <Loading />
      </AppPage>
    );
  }

  if (!authEnabled || currentUser?.role !== 'admin') {
    return <Navigate to="/" replace />;
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const runPending = async () => {
    if (!pending) return;
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      if (pending.type === 'disable') {
        await adminUsersApi.disable(pending.user.id);
        setSuccess(t('adminUsers.disableSuccess'));
      } else if (pending.type === 'enable') {
        await adminUsersApi.update(pending.user.id, { status: 'active' });
        setSuccess(t('adminUsers.enableSuccess'));
      } else if (pending.type === 'role') {
        await adminUsersApi.update(pending.user.id, { role: pending.role });
        setSuccess(t('adminUsers.roleSuccess'));
      } else if (pending.type === 'reset') {
        await adminUsersApi.resetPassword(pending.user.id, pending.password);
        setSuccess(t('adminUsers.resetSuccess'));
        setResetTarget(null);
        setResetPassword('');
        setResetPasswordConfirm('');
      } else if (pending.type === 'revoke') {
        await adminUsersApi.revokeSessions(pending.user.id);
        setSuccess(t('adminUsers.revokeSuccess'));
      }
      await loadUsers();
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setBusy(false);
      setPending(null);
    }
  };

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    setCreatedOnceHint(null);
    const username = createUsername.trim();
    if (!username) {
      setError(createParsedApiError({
        title: t('adminUsers.createFailure'),
        message: t('adminUsers.createUsernameRequired'),
        category: 'unknown',
      }));
      return;
    }
    if (createPassword.length < 6) {
      setError(createParsedApiError({
        title: t('adminUsers.createFailure'),
        message: t('adminUsers.createPasswordShort'),
        category: 'unknown',
      }));
      return;
    }
    setBusy(true);
    try {
      const body: CreateAdminUserRequest = {
        username,
        password: createPassword,
        role: createRole,
      };
      const created = await adminUsersApi.create(body);
      setCreatedOnceHint(t('adminUsers.createOnceHint', { username: created.username }));
      setCreateUsername('');
      setCreatePassword('');
      setCreateRole('user');
      setSuccess(t('adminUsers.createSuccess'));
      await loadUsers();
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setBusy(false);
    }
  };

  const confirmMessage = (() => {
    if (!pending) return '';
    if (pending.type === 'disable') return t('adminUsers.confirmDisable', { username: pending.user.username });
    if (pending.type === 'enable') return t('adminUsers.confirmEnable', { username: pending.user.username });
    if (pending.type === 'role') {
      return t('adminUsers.confirmRole', {
        username: pending.user.username,
        role: pending.role === 'admin' ? t('account.roleAdmin') : t('account.roleUser'),
      });
    }
    if (pending.type === 'reset') return t('adminUsers.confirmReset', { username: pending.user.username });
    return t('adminUsers.confirmRevoke', { username: pending.user.username });
  })();

  return (
    <AppPage>
      <PageHeader title={t('adminUsers.title')} description={t('adminUsers.description')} />

      {error ? <ApiErrorAlert error={error} className="mb-4" /> : null}
      {success ? (
        <InlineAlert
          variant="success"
          title={t('adminUsers.actionSuccessTitle')}
          message={success}
          className="mb-4"
        />
      ) : null}
      {createdOnceHint ? (
        <InlineAlert
          variant="warning"
          title={t('adminUsers.createOnceTitle')}
          message={createdOnceHint}
          className="mb-4"
        />
      ) : null}

      <div className="space-y-4">
        <Card padding="md" className="rounded-xl">
          <h2 className="text-base font-semibold text-foreground">{t('adminUsers.createTitle')}</h2>
          <p className="mt-1 text-sm text-secondary-text">{t('adminUsers.createDescription')}</p>
          <form onSubmit={handleCreate} className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <Input
              id="admin-create-username"
              label={t('adminUsers.username')}
              value={createUsername}
              onChange={(e) => setCreateUsername(e.target.value)}
              autoComplete="off"
              disabled={busy}
            />
            <Input
              id="admin-create-password"
              type="password"
              allowTogglePassword
              iconType="password"
              label={t('adminUsers.password')}
              value={createPassword}
              onChange={(e) => setCreatePassword(e.target.value)}
              autoComplete="new-password"
              disabled={busy}
            />
            <Select
              id="admin-create-role"
              label={t('adminUsers.role')}
              value={createRole}
              onChange={(value) => setCreateRole(value as 'user' | 'admin')}
              disabled={busy}
              options={[
                { value: 'user', label: t('account.roleUser') },
                { value: 'admin', label: t('account.roleAdmin') },
              ]}
            />
            <div className="flex items-end">
              <Button type="submit" variant="primary" isLoading={busy} className="w-full">
                {t('adminUsers.createSubmit')}
              </Button>
            </div>
          </form>
        </Card>

        <Card padding="md" className="rounded-xl">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div className="grid flex-1 gap-3 sm:grid-cols-3">
              <Input
                id="admin-search"
                label={t('adminUsers.search')}
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    setPage(1);
                    setSearch(searchInput.trim());
                  }
                }}
              />
              <Select
                id="admin-role-filter"
                label={t('adminUsers.roleFilter')}
                value={roleFilter}
                onChange={(value) => {
                  setPage(1);
                  setRoleFilter(value);
                }}
                options={[
                  { value: '', label: t('adminUsers.filterAll') },
                  { value: 'admin', label: t('account.roleAdmin') },
                  { value: 'user', label: t('account.roleUser') },
                ]}
              />
              <Select
                id="admin-status-filter"
                label={t('adminUsers.statusFilter')}
                value={statusFilter}
                onChange={(value) => {
                  setPage(1);
                  setStatusFilter(value);
                }}
                options={[
                  { value: '', label: t('adminUsers.filterAll') },
                  { value: 'active', label: t('account.statusActive') },
                  { value: 'disabled', label: t('account.statusDisabled') },
                ]}
              />
            </div>
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setPage(1);
                setSearch(searchInput.trim());
              }}
            >
              {t('common.search')}
            </Button>
          </div>

          {loading ? (
            <div className="mt-6">
              <Loading />
            </div>
          ) : items.length === 0 ? (
            <div className="mt-6">
              <EmptyState title={t('adminUsers.emptyTitle')} description={t('adminUsers.emptyDescription')} />
            </div>
          ) : (
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="border-b border-border/70 text-xs text-secondary-text">
                  <tr>
                    <th className="px-2 py-2 font-medium">{t('adminUsers.username')}</th>
                    <th className="px-2 py-2 font-medium">{t('adminUsers.role')}</th>
                    <th className="px-2 py-2 font-medium">{t('adminUsers.status')}</th>
                    <th className="px-2 py-2 font-medium">{t('adminUsers.lastLogin')}</th>
                    <th className="px-2 py-2 font-medium">{t('adminUsers.actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((user) => (
                    <tr key={user.id} className="border-b border-border/40 align-top">
                      <td className="px-2 py-3">
                        <div className="font-medium text-foreground">{user.username}</div>
                        <div className="text-xs text-secondary-text">#{user.id}</div>
                      </td>
                      <td className="px-2 py-3">
                        <Badge variant={user.role === 'admin' ? 'info' : 'default'}>
                          {user.role === 'admin' ? t('account.roleAdmin') : t('account.roleUser')}
                        </Badge>
                      </td>
                      <td className="px-2 py-3">
                        <Badge variant={user.status === 'active' ? 'success' : 'danger'}>
                          {user.status === 'disabled' ? t('account.statusDisabled') : t('account.statusActive')}
                        </Badge>
                      </td>
                      <td className="px-2 py-3 text-secondary-text">{user.lastLoginAt || '-'}</td>
                      <td className="px-2 py-3">
                        <div className="flex min-w-[16rem] flex-wrap gap-2">
                          {user.status === 'active' ? (
                            <Button
                              type="button"
                              size="sm"
                              variant="danger"
                              disabled={busy || user.id === currentUser?.id}
                              onClick={() => setPending({ type: 'disable', user })}
                            >
                              {t('adminUsers.disable')}
                            </Button>
                          ) : (
                            <Button
                              type="button"
                              size="sm"
                              variant="secondary"
                              disabled={busy}
                              onClick={() => setPending({ type: 'enable', user })}
                            >
                              {t('adminUsers.enable')}
                            </Button>
                          )}
                          <Button
                            type="button"
                            size="sm"
                            variant="secondary"
                            disabled={busy}
                            onClick={() =>
                              setPending({
                                type: 'role',
                                user,
                                role: user.role === 'admin' ? 'user' : 'admin',
                              })
                            }
                          >
                            {user.role === 'admin' ? t('adminUsers.demote') : t('adminUsers.promote')}
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="secondary"
                            disabled={busy}
                            onClick={() => {
                              setResetTarget(user);
                              setResetPassword('');
                              setResetPasswordConfirm('');
                            }}
                          >
                            {t('adminUsers.resetPassword')}
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="secondary"
                            disabled={busy}
                            onClick={() => setPending({ type: 'revoke', user })}
                          >
                            {t('adminUsers.revokeSessions')}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {totalPages > 1 ? (
            <div className="mt-4">
              <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage} />
            </div>
          ) : null}
        </Card>

        {resetTarget ? (
          <Card padding="md" className="rounded-xl">
            <h2 className="text-base font-semibold text-foreground">
              {t('adminUsers.resetTitle', { username: resetTarget.username })}
            </h2>
            <p className="mt-1 text-sm text-secondary-text">{t('adminUsers.resetDescription')}</p>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <Input
                id="admin-reset-password"
                type="password"
                allowTogglePassword
                iconType="password"
                label={t('adminUsers.password')}
                value={resetPassword}
                onChange={(e) => setResetPassword(e.target.value)}
                autoComplete="new-password"
              />
              <Input
                id="admin-reset-password-confirm"
                type="password"
                allowTogglePassword
                iconType="password"
                label={t('adminUsers.passwordConfirm')}
                value={resetPasswordConfirm}
                onChange={(e) => setResetPasswordConfirm(e.target.value)}
                autoComplete="new-password"
              />
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button
                type="button"
                variant="primary"
                disabled={busy}
                onClick={() => {
                  if (resetPassword.length < 6) {
                    setError(createParsedApiError({
                      title: t('adminUsers.resetFailure'),
                      message: t('adminUsers.createPasswordShort'),
                      category: 'unknown',
                    }));
                    return;
                  }
                  if (resetPassword !== resetPasswordConfirm) {
                    setError(createParsedApiError({
                      title: t('adminUsers.resetFailure'),
                      message: t('login.passwordMismatch'),
                      category: 'unknown',
                    }));
                    return;
                  }
                  setPending({ type: 'reset', user: resetTarget, password: resetPassword });
                }}
              >
                {t('adminUsers.resetSubmit')}
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setResetTarget(null);
                  setResetPassword('');
                  setResetPasswordConfirm('');
                }}
              >
                {t('common.cancel')}
              </Button>
            </div>
          </Card>
        ) : null}
      </div>

      <ConfirmDialog
        isOpen={pending != null}
        title={t('adminUsers.confirmTitle')}
        message={confirmMessage}
        confirmText={t('common.confirm')}
        cancelText={t('common.cancel')}
        isDanger={pending?.type === 'disable' || pending?.type === 'reset'}
        onConfirm={() => {
          void runPending();
        }}
        onCancel={() => setPending(null)}
      />
    </AppPage>
  );
};

export default AdminUsersPage;
