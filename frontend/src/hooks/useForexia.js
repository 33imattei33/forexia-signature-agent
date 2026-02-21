/**
 * ═══════════════════════════════════════════════════════════════════
 *  FOREXIA SIGNATURE AGENT — API HOOKS
 *  React hooks for communicating with the Python backend
 * ═══════════════════════════════════════════════════════════════════
 */

import { useState, useEffect, useCallback } from 'react';

const API_BASE = '';
const POLL_INTERVAL = 2000; // 2 seconds — real-time P&L sync

/**
 * Core fetch wrapper with error handling
 */
async function apiFetch(endpoint, options = {}) {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error(`API Error [${endpoint}]:`, err);
    return null;
  }
}

/**
 * Hook: Poll the full dashboard state every N seconds
 */
export function useDashboard() {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const result = await apiFetch('/api/dashboard');
      if (result) {
        setDashboard(result);
        setError(null);
      } else {
        setError('Failed to fetch dashboard');
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [refresh]);

  // Derive sub-data from the dashboard response
  const signals = dashboard?.active_signals || [];
  const trades = dashboard?.recent_trades || [];
  const news = dashboard?.upcoming_catalysts || [];
  const liquidity = dashboard?.liquidity_zones || [];

  return { dashboard, signals, trades, news, liquidity, loading, error, refresh };
}

/**
 * Hook: Session and phase information
 */
export function useSession() {
  const [session, setSession] = useState(null);
  const [multiPair, setMultiPair] = useState(null);

  useEffect(() => {
    const fetchSession = async () => {
      const result = await apiFetch('/api/session');
      if (result) setSession(result);
    };
    const fetchMultiPair = async () => {
      const result = await apiFetch('/api/multi-pair');
      if (result) setMultiPair(result);
    };
    fetchSession();
    fetchMultiPair();
    const interval = setInterval(() => {
      fetchSession();
      fetchMultiPair();
    }, 3000); // 3s — session/multi-pair sync
    return () => clearInterval(interval);
  }, []);

  return { session, multiPair };
}

/**
 * Hook: Control actions (close all, reset, trauma filter)
 */
export function useControls() {
  const closeAll = () => apiFetch('/api/close-all', { method: 'POST' });
  const resetDaily = () => apiFetch('/api/reset/daily', { method: 'POST' });
  const resetWeekly = () => apiFetch('/api/reset/weekly', { method: 'POST' });
  const scrapeNews = () => apiFetch('/api/scrape-news', { method: 'POST' });
  const armTrauma = () => apiFetch('/api/trauma/arm', { method: 'POST' });
  const disarmTrauma = () => apiFetch('/api/trauma/disarm', { method: 'POST' });

  return { closeAll, resetDaily, resetWeekly, scrapeNews, armTrauma, disarmTrauma };
}

/**
 * Hook: System health
 */
export function useHealth() {
  const [healthy, setHealthy] = useState(false);
  const [latency, setLatency] = useState(0);

  useEffect(() => {
    const check = async () => {
      const start = Date.now();
      const result = await apiFetch('/health');
      const elapsed = Date.now() - start;
      if (result && result.status === 'OPERATIONAL') {
        setHealthy(true);
        setLatency(elapsed);
      } else {
        setHealthy(false);
      }
    };
    check();
    const interval = setInterval(check, 10000);
    return () => clearInterval(interval);
  }, []);

  return { healthy, latency };
}
