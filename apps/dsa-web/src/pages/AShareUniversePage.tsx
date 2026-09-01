import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Database, RefreshCw, Search } from 'lucide-react';
import {
  universeApi,
  type AShareUniverseItem,
  type AShareUniverseStats,
} from '../api/universe';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import {
  ApiErrorAlert,
  AppPage,
  Badge,
  Button,
  Card,
  EmptyState,
  InlineAlert,
  Input,
  Loading,
  PageHeader,
  Pagination,
  StatCard,
} from '../components/common';
import { useAuth } from '../contexts/AuthContext';
import { useUiLanguage } from '../contexts/UiLanguageContext';

const PAGE_SIZE = 50;
const STATS_POLL_MS = 5000;

function formatDateTime(value: string | null | undefined, locale: string): string {
  if (!value) {
    return '-';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(locale, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function formatDuration(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const secs = safe % 60;
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  if (minutes > 0) {
    return `${minutes}m ${secs}s`;
  }
  return `${secs}s`;
}

const AShareUniversePage: React.FC = () => {
  const { t, language } = useUiLanguage();
  const { currentUser } = useAuth();
  const isAdmin = currentUser?.role === 'admin';

  const [stats, setStats] = useState<AShareUniverseStats | null>(null);
  const [items, setItems] = useState<AShareUniverseItem[]>([]);
  const [resultTotal, setResultTotal] = useState(0);
  const [queryInput, setQueryInput] = useState('');
  const [activeQuery, setActiveQuery] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const locale = language === 'en' ? 'en-US' : 'zh-CN';

  const loadStats = useCallback(async () => {
    try {
      const data = await universeApi.getStats();
      setStats(data);
      return data;
    } catch (err) {
      setError(getParsedApiError(err));
      return null;
    }
  }, []);

  const loadResults = useCallback(async (query: string, pageNumber: number) => {
    setSearching(true);
    setError(null);
    try {
      const data = await universeApi.search({
        q: query,
        limit: PAGE_SIZE,
        offset: (pageNumber - 1) * PAGE_SIZE,
      });
      setItems(data.items);
      setResultTotal(data.total);
    } catch (err) {
      setError(getParsedApiError(err));
      setItems([]);
      setResultTotal(0);
    } finally {
      setSearching(false);
    }
  }, []);

  useEffect(() => {
    document.title = t('aShareUniverse.pageTitle');
  }, [t]);

  useEffect(() => {
    let active = true;
    const bootstrap = async () => {
      setLoading(true);
      await loadStats();
      if (active) {
        setLoading(false);
      }
    };
    void bootstrap();
    return () => {
      active = false;
    };
  }, [loadStats]);

  useEffect(() => {
    void loadResults(activeQuery, page);
  }, [activeQuery, page, loadResults]);

  useEffect(() => {
    if (stats?.sync_status !== 'running') {
      if (pollRef.current !== null) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return undefined;
    }

    pollRef.current = window.setInterval(() => {
      void loadStats().then((next) => {
        if (next && next.sync_status !== 'running') {
          void loadResults(activeQuery, page);
        }
      });
    }, STATS_POLL_MS);

    return () => {
      if (pollRef.current !== null) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [activeQuery, loadResults, loadStats, page, stats?.sync_status]);

  const syncDisabledReason = useMemo(() => {
    if (!isAdmin) {
      return t('aShareUniverse.sync.adminOnly');
    }
    if (!stats) {
      return t('aShareUniverse.sync.loading');
    }
    if (stats.sync_status === 'running' || syncing) {
      return t('aShareUniverse.sync.running');
    }
    if (stats.sync_status === 'cooldown' && stats.cooldown_remaining_seconds > 0) {
      return t('aShareUniverse.sync.cooldown', {
        duration: formatDuration(stats.cooldown_remaining_seconds),
      });
    }
    return null;
  }, [isAdmin, stats, syncing, t]);

  const handleSearch = (event: React.FormEvent) => {
    event.preventDefault();
    setPage(1);
    setActiveQuery(queryInput.trim());
  };

  const handleManualSync = async () => {
    if (syncDisabledReason) {
      return;
    }
    setSyncing(true);
    setError(null);
    setSuccess(null);
    try {
      const response = await universeApi.triggerManualSync();
      setSuccess(response.message || t('aShareUniverse.sync.started'));
      const nextStats = await loadStats();
      if (nextStats?.sync_status === 'running') {
        // polling effect will keep refreshing
      }
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setSyncing(false);
    }
  };

  const totalPages = Math.max(1, Math.ceil(resultTotal / PAGE_SIZE));

  const statusBadge = (() => {
    const status = stats?.sync_status ?? 'idle';
    if (status === 'running') {
      return <Badge variant="info">{t('aShareUniverse.status.running')}</Badge>;
    }
    if (status === 'cooldown') {
      return <Badge variant="warning">{t('aShareUniverse.status.cooldown')}</Badge>;
    }
    return <Badge variant="success">{t('aShareUniverse.status.idle')}</Badge>;
  })();

  if (loading) {
    return (
      <AppPage>
        <Loading label={t('common.loading')} />
      </AppPage>
    );
  }

  return (
    <AppPage>
      <PageHeader
        title={t('aShareUniverse.title')}
        description={t('aShareUniverse.description')}
        actions={(
          <div className="flex flex-wrap items-center gap-2">
            {statusBadge}
            {isAdmin ? (
              <Button
                type="button"
                variant="primary"
                disabled={Boolean(syncDisabledReason)}
                onClick={() => void handleManualSync()}
              >
                <RefreshCw className={`mr-2 h-4 w-4 ${stats?.sync_status === 'running' ? 'animate-spin' : ''}`} />
                {t('aShareUniverse.sync.action')}
              </Button>
            ) : null}
          </div>
        )}
      />

      {error ? <ApiErrorAlert error={error} className="mb-4" /> : null}
      {success ? <InlineAlert variant="success" className="mb-4" message={success} /> : null}
      {syncDisabledReason && isAdmin ? (
        <InlineAlert variant="info" className="mb-4" message={syncDisabledReason} />
      ) : null}
      {stats?.last_error ? (
        <InlineAlert
          variant="warning"
          className="mb-4"
          message={t('aShareUniverse.lastError', { message: stats.last_error })}
        />
      ) : null}

      <div className="mb-6 grid gap-4 md:grid-cols-3">
        <StatCard
          icon={<Database className="h-5 w-5" />}
          label={t('aShareUniverse.stats.total')}
          value={String(stats?.total_count ?? 0)}
          hint={t('aShareUniverse.stats.totalHint')}
        />
        <StatCard
          icon={<RefreshCw className="h-5 w-5" />}
          label={t('aShareUniverse.stats.lastSuccess')}
          value={formatDateTime(stats?.last_success_at, locale)}
          hint={t('aShareUniverse.stats.manualOnlyHint')}
        />
        <StatCard
          icon={<Search className="h-5 w-5" />}
          label={t('aShareUniverse.stats.mode')}
          value={stats?.auto_sync_enabled ? t('aShareUniverse.stats.autoEnabled') : t('aShareUniverse.stats.manualOnly')}
          hint={t('aShareUniverse.stats.cooldownHint', { minutes: Math.floor((stats?.cooldown_seconds ?? 3600) / 60) })}
        />
      </div>

      <Card className="mb-6" padding="md">
        <form className="flex flex-col gap-3 md:flex-row" onSubmit={handleSearch}>
          <Input
            value={queryInput}
            onChange={(event) => setQueryInput(event.target.value)}
            placeholder={t('aShareUniverse.searchPlaceholder')}
            aria-label={t('aShareUniverse.searchPlaceholder')}
          />
          <Button type="submit" variant="secondary" disabled={searching}>
            <Search className="mr-2 h-4 w-4" />
            {t('aShareUniverse.searchAction')}
          </Button>
        </form>
      </Card>

      <Card padding="none" className="overflow-hidden">
        {searching ? (
          <div className="p-8">
            <Loading label={t('common.loading')} />
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            title={t('aShareUniverse.emptyTitle')}
            description={t('aShareUniverse.emptyDescription')}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="border-b border-border/70 bg-muted/40 text-left text-secondary-text">
                <tr>
                  <th className="px-4 py-3 font-medium">{t('aShareUniverse.table.code')}</th>
                  <th className="px-4 py-3 font-medium">{t('aShareUniverse.table.name')}</th>
                  <th className="px-4 py-3 font-medium">{t('aShareUniverse.table.exchange')}</th>
                  <th className="px-4 py-3 font-medium">{t('aShareUniverse.table.board')}</th>
                  <th className="px-4 py-3 font-medium">{t('aShareUniverse.table.industry')}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.canonical_code} className="border-b border-border/50 last:border-b-0">
                    <td className="px-4 py-3 font-mono text-foreground">{item.canonical_code}</td>
                    <td className="px-4 py-3 text-foreground">{item.name}</td>
                    <td className="px-4 py-3 text-secondary-text">{item.exchange}</td>
                    <td className="px-4 py-3 text-secondary-text">{item.board || '-'}</td>
                    <td className="px-4 py-3 text-secondary-text">{item.industry || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <div className="mt-4 flex justify-end">
        <Pagination
          currentPage={page}
          totalPages={totalPages}
          onPageChange={setPage}
        />
      </div>
    </AppPage>
  );
};

export default AShareUniversePage;
