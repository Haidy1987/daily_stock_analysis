import type React from 'react';
import { useEffect, useState } from 'react';
import { ApiErrorAlert, AppPage, Button, Card, ConfirmDialog, InlineAlert, PageHeader } from '../components/common';
import { ChangePasswordCard } from '../components/settings/ChangePasswordCard';
import { useAuth } from '../contexts/AuthContext';
import { useUiLanguage } from '../contexts/UiLanguageContext';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';

const AccountPage: React.FC = () => {
  const { t } = useUiLanguage();
  const {
    authEnabled,
    currentUser,
    passwordChangeable,
    logoutAll,
    refreshStatus,
  } = useAuth();
  const [showLogoutAllConfirm, setShowLogoutAllConfirm] = useState(false);
  const [logoutAllBusy, setLogoutAllBusy] = useState(false);
  const [actionError, setActionError] = useState<ParsedApiError | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  useEffect(() => {
    document.title = t('account.pageTitle');
  }, [t]);

  useEffect(() => {
    void refreshStatus();
  }, [refreshStatus]);

  const handleLogoutAll = async () => {
    setActionError(null);
    setActionSuccess(null);
    setLogoutAllBusy(true);
    try {
      await logoutAll();
      setActionSuccess(t('account.logoutAllSuccess'));
    } catch (err) {
      setActionError(getParsedApiError(err));
    } finally {
      setLogoutAllBusy(false);
      setShowLogoutAllConfirm(false);
    }
  };

  if (!authEnabled) {
    return (
      <AppPage>
        <PageHeader title={t('account.title')} description={t('account.description')} />
        <InlineAlert
          variant="info"
          title={t('account.authDisabledTitle')}
          message={t('account.authDisabledMessage')}
        />
      </AppPage>
    );
  }

  return (
    <AppPage>
      <PageHeader title={t('account.title')} description={t('account.description')} />

      {actionError ? <ApiErrorAlert error={actionError} className="mb-4" /> : null}
      {actionSuccess ? (
        <InlineAlert
          variant="success"
          title={t('account.actionSuccessTitle')}
          message={actionSuccess}
          className="mb-4"
        />
      ) : null}

      <div className="space-y-4">
        <Card padding="md" className="rounded-xl">
          <h2 className="text-base font-semibold text-foreground">{t('account.profileTitle')}</h2>
          <p className="mt-1 text-sm text-secondary-text">{t('account.profileDescription')}</p>
          <dl className="mt-4 grid gap-3 sm:grid-cols-2">
            <div>
              <dt className="text-xs text-secondary-text">{t('account.username')}</dt>
              <dd className="mt-1 text-sm font-medium text-foreground">{currentUser?.username ?? '-'}</dd>
            </div>
            <div>
              <dt className="text-xs text-secondary-text">{t('account.role')}</dt>
              <dd className="mt-1 text-sm font-medium text-foreground">
                {currentUser?.role === 'admin' ? t('account.roleAdmin') : t('account.roleUser')}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-secondary-text">{t('account.status')}</dt>
              <dd className="mt-1 text-sm font-medium text-foreground">
                {currentUser?.status === 'disabled' ? t('account.statusDisabled') : t('account.statusActive')}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-secondary-text">{t('account.userId')}</dt>
              <dd className="mt-1 text-sm font-medium text-foreground">{currentUser?.id ?? '-'}</dd>
            </div>
          </dl>
        </Card>

        {passwordChangeable ? <ChangePasswordCard /> : null}

        <Card padding="md" className="rounded-xl">
          <h2 className="text-base font-semibold text-foreground">{t('account.sessionsTitle')}</h2>
          <p className="mt-1 text-sm text-secondary-text">{t('account.sessionsDescription')}</p>
          <div className="mt-4">
            <Button
              type="button"
              variant="danger"
              onClick={() => setShowLogoutAllConfirm(true)}
              disabled={logoutAllBusy}
            >
              {t('account.logoutAll')}
            </Button>
          </div>
        </Card>
      </div>

      <ConfirmDialog
        isOpen={showLogoutAllConfirm}
        title={t('account.logoutAllTitle')}
        message={t('account.logoutAllMessage')}
        confirmText={t('account.logoutAllConfirm')}
        cancelText={t('common.cancel')}
        isDanger
        onConfirm={() => {
          void handleLogoutAll();
        }}
        onCancel={() => setShowLogoutAllConfirm(false)}
      />
    </AppPage>
  );
};

export default AccountPage;
