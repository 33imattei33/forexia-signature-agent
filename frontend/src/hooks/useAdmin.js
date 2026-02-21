/**
 * ═══════════════════════════════════════════════════════════════════
 *  FOREXIA — SUPER ADMIN HOOKS
 *  API hooks for the admin dashboard
 * ═══════════════════════════════════════════════════════════════════
 */
import { useState, useEffect, useCallback } from 'react';

const API_BASE = '';

async function apiFetch(endpoint, options = {}) {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error(`Admin API Error [${endpoint}]:`, err);
    return null;
  }
}

/** Poll admin overview every 3s */
export function useAdminOverview() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const result = await apiFetch('/api/admin/overview');
      if (result) { setData(result); setError(null); }
      else { setError('Failed to fetch admin overview'); }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, 3000);
    return () => clearInterval(iv);
  }, [refresh]);

  return { data, loading, error, refresh };
}

/** Poll performance data every 10s */
export function useAdminPerformance() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const result = await apiFetch('/api/admin/performance');
      if (result) { setData(result); setError(null); }
      else { setError('Failed to fetch performance data'); }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, 10000);
    return () => clearInterval(iv);
  }, [refresh]);

  return { data, loading, error, refresh };
}

/** Admin actions */
export function useAdminActions() {
  const updateSettings = (settings) =>
    apiFetch('/api/admin/settings', { method: 'PUT', body: JSON.stringify(settings) });

  const updatePairBlacklist = (blacklist) =>
    apiFetch('/api/admin/pair-blacklist', { method: 'POST', body: JSON.stringify({ blacklist }) });

  const getPairBlacklist = () => apiFetch('/api/admin/pair-blacklist');

  const resetConsecutiveLosses = () =>
    apiFetch('/api/admin/reset-consecutive', { method: 'POST' });

  const getAiWorkflow = () => apiFetch('/api/admin/ai-workflow');

  const updateAiConfig = (config) =>
    apiFetch('/api/admin/ai-config', { method: 'POST', body: JSON.stringify(config) });

  const getLogs = () => apiFetch('/api/admin/logs');

  const toggleBot = () => apiFetch('/api/bot/toggle', { method: 'POST' });
  const triggerScan = () => apiFetch('/api/bot/scan', { method: 'POST' });
  const closeAll = () => apiFetch('/api/close-all', { method: 'POST' });
  const resetDaily = () => apiFetch('/api/reset/daily', { method: 'POST' });

  return {
    updateSettings, updatePairBlacklist, getPairBlacklist,
    resetConsecutiveLosses, getAiWorkflow, updateAiConfig,
    getLogs, toggleBot, triggerScan, closeAll, resetDaily,
  };
}
