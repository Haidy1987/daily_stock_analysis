import type React from 'react';
import { useEffect } from 'react';
import { BrowserRouter as Router, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { lazyWithRetry } from './utils/lazyWithRetry';
import { ApiErrorAlert, Shell } from './components/common';
import {
  PageLoadingFallback,
  RouteOutletBoundary,
  StandaloneRouteBoundary,
} from './components/layout/RouteBoundary';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { UiLanguageProvider, useUiLanguage } from './contexts/UiLanguageContext';
import { useAgentChatStore } from './stores/agentChatStore';
import './App.css';

const HomePage = lazyWithRetry(() => import('./pages/HomePage'), 'pages/HomePage');
const BacktestPage = lazyWithRetry(() => import('./pages/BacktestPage'), 'pages/BacktestPage');
const SettingsPage = lazyWithRetry(() => import('./pages/SettingsPage'), 'pages/SettingsPage');
const LoginPage = lazyWithRetry(() => import('./pages/LoginPage'), 'pages/LoginPage');
const NotFoundPage = lazyWithRetry(() => import('./pages/NotFoundPage'), 'pages/NotFoundPage');
const ChatPage = lazyWithRetry(() => import('./pages/ChatPage'), 'pages/ChatPage');
const PortfolioPage = lazyWithRetry(() => import('./pages/PortfolioPage'), 'pages/PortfolioPage');
const DecisionSignalsPage = lazyWithRetry(() => import('./pages/DecisionSignalsPage'), 'pages/DecisionSignalsPage');
const AlertsPage = lazyWithRetry(() => import('./pages/AlertsPage'), 'pages/AlertsPage');
const TokenUsagePage = lazyWithRetry(() => import('./pages/TokenUsagePage'), 'pages/TokenUsagePage');
const StockScreeningPage = lazyWithRetry(() => import('./pages/StockScreeningPage'), 'pages/StockScreeningPage');
const AccountPage = lazyWithRetry(() => import('./pages/AccountPage'), 'pages/AccountPage');
const AdminUsersPage = lazyWithRetry(() => import('./pages/AdminUsersPage'), 'pages/AdminUsersPage');
const TechnicalChartPage = lazyWithRetry(() => import('./pages/TechnicalChartPage'), 'pages/TechnicalChartPage');
const AShareUniversePage = lazyWithRetry(() => import('./pages/AShareUniversePage'), 'pages/AShareUniversePage');

const AppContent: React.FC = () => {
  const location = useLocation();
  const { authEnabled, loggedIn, isLoading, loadError, refreshStatus } = useAuth();
  const { t } = useUiLanguage();

  useEffect(() => {
    useAgentChatStore.getState().setCurrentRoute(location.pathname);
  }, [location.pathname]);

  if (isLoading) {
    return <PageLoadingFallback />;
  }

  if (loadError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-base px-4">
        <div className="w-full max-w-lg">
          <ApiErrorAlert error={loadError} />
        </div>
        <button
          type="button"
          className="btn-primary"
          onClick={() => void refreshStatus()}
        >
          {t('common.retry')}
        </button>
      </div>
    );
  }

  if (authEnabled && !loggedIn) {
    if (location.pathname === '/login') {
      return (
        <StandaloneRouteBoundary>
          <LoginPage />
        </StandaloneRouteBoundary>
      );
    }
    const redirect = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?redirect=${redirect}`} replace />;
  }

  if (location.pathname === '/login') {
    return <Navigate to="/" replace />;
  }

  return (
    <Routes>
      <Route
        element={(
          <Shell>
            <RouteOutletBoundary />
          </Shell>
        )}
      >
        <Route path="/" element={<HomePage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/decision-signals" element={<DecisionSignalsPage />} />
        <Route path="/screening" element={<StockScreeningPage />} />
        <Route path="/technical-chart" element={<TechnicalChartPage />} />
        <Route path="/a-share-universe" element={<AShareUniversePage />} />
        <Route path="/backtest" element={<BacktestPage />} />
        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="/usage" element={<TokenUsagePage />} />
        <Route path="/account" element={<AccountPage />} />
        <Route path="/admin/users" element={<AdminUsersPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
};

const App: React.FC = () => {
  return (
    <UiLanguageProvider>
      <Router>
        <AuthProvider>
          <AppContent />
        </AuthProvider>
      </Router>
    </UiLanguageProvider>
  );
};

export default App;
