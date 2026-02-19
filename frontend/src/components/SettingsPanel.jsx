/**
 * ═══════════════════════════════════════════════════════════════════
 *  FOREXIA — SETTINGS PANEL
 *  Configure broker connection (MT4/MT5), risk params, and agent behavior
 * ═══════════════════════════════════════════════════════════════════
 */
import React, { useState, useEffect, useCallback } from 'react';

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
    console.error(`Settings API Error [${endpoint}]:`, err);
    return null;
  }
}

/* ───── Section Header ───── */
function SectionHeader({ title, subtitle }) {
  return (
    <div className="mb-4">
      <h3 className="text-xs uppercase tracking-widest text-forexia-accent font-bold">{title}</h3>
      {subtitle && <p className="text-[10px] text-gray-600 mt-1">{subtitle}</p>}
    </div>
  );
}

/* ───── Input Field ───── */
function Field({ label, type = 'text', value, onChange, placeholder, description, disabled }) {
  return (
    <div className="mb-3">
      <label className="block text-[10px] uppercase tracking-wider text-gray-500 mb-1">{label}</label>
      <input
        type={type}
        value={value ?? ''}
        onChange={(e) => onChange(type === 'number' ? parseFloat(e.target.value) || 0 : e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className="w-full bg-gray-900/80 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-forexia-accent/50 transition-colors disabled:opacity-40"
      />
      {description && <p className="text-[9px] text-gray-600 mt-1">{description}</p>}
    </div>
  );
}

/* ───── Toggle Switch ───── */
function Toggle({ label, checked, onChange, description }) {
  return (
    <div className="flex items-center justify-between mb-3 py-1">
      <div>
        <span className="text-[10px] uppercase tracking-wider text-gray-500">{label}</span>
        {description && <p className="text-[9px] text-gray-600 mt-0.5">{description}</p>}
      </div>
      <button
        onClick={() => onChange(!checked)}
        className={`relative w-10 h-5 rounded-full transition-colors ${
          checked ? 'bg-forexia-accent' : 'bg-gray-700'
        }`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform ${
            checked ? 'translate-x-5' : ''
          }`}
        />
      </button>
    </div>
  );
}

/* ───── Select Dropdown ───── */
function Select({ label, value, onChange, options, description }) {
  return (
    <div className="mb-3">
      <label className="block text-[10px] uppercase tracking-wider text-gray-500 mb-1">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-gray-900/80 border border-gray-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-forexia-accent/50"
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
      {description && <p className="text-[9px] text-gray-600 mt-1">{description}</p>}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
 *  SETTINGS PANEL — Main Component
 * ═══════════════════════════════════════════════════════════════════ */
export default function SettingsPanel({ isOpen, onClose }) {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [message, setMessage] = useState(null);
  const [passwordEdited, setPasswordEdited] = useState(false);
  const [mtPasswordEdited, setMtPasswordEdited] = useState(false);
  const [e8QuickMode, setE8QuickMode] = useState(false);
  const [e8Email, setE8Email] = useState('');
  const [e8Password, setE8Password] = useState('');
  const [propFirmMode, setPropFirmMode] = useState(null); // 'APEX'|'GET_LEVERAGED'|'DNA_FUNDED'|null
  const [propFirmCreds, setPropFirmCreds] = useState({ login: '', password: '', server: '', mt5_path: '' });

  // Load settings
  const loadSettings = useCallback(async () => {
    setLoading(true);
    const result = await apiFetch('/api/settings');
    if (result) {
      setSettings(result);
      setPasswordEdited(false);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    if (isOpen) loadSettings();
  }, [isOpen, loadSettings]);

  // Helper to update nested state
  const updateBroker = (key, val) => {
    setSettings((s) => ({ ...s, broker: { ...s.broker, [key]: val } }));
    if (key === 'password') setPasswordEdited(true);
    if (key === 'matchtrader_password') setMtPasswordEdited(true);
  };
  const updateRisk = (key, val) => setSettings((s) => ({ ...s, risk: { ...s.risk, [key]: val } }));
  const updateAgent = (key, val) => setSettings((s) => ({ ...s, agent: { ...s.agent, [key]: val } }));

  // Save settings
  const handleSave = async () => {
    setSaving(true);
    setMessage(null);

    const payload = { ...settings };
    // Don't send masked passwords unless user edited them
    if (!passwordEdited) {
      payload.broker = { ...payload.broker };
      delete payload.broker.password;
    }
    if (!mtPasswordEdited) {
      payload.broker = { ...payload.broker };
      delete payload.broker.matchtrader_password;
    }

    const result = await apiFetch('/api/settings', {
      method: 'PUT',
      body: JSON.stringify(payload),
    });

    if (result?.status === 'OK') {
      setMessage({ type: 'success', text: 'Settings saved successfully' });
      setPasswordEdited(false);
      setMtPasswordEdited(false);
    } else {
      setMessage({ type: 'error', text: 'Failed to save settings' });
    }
    setSaving(false);
  };

  // Connect to broker
  const handleConnect = async () => {
    setConnecting(true);
    setMessage(null);

    // Save first
    await handleSave();

    const result = await apiFetch('/api/settings/connect', { method: 'POST' });
    if (result?.connected) {
      setMessage({
        type: 'success',
        text: `Connected to ${result.platform.toUpperCase()} — Balance: $${result.balance?.toFixed(2)}, Equity: $${result.equity?.toFixed(2)}`,
      });
    } else {
      setMessage({
        type: 'error',
        text: result?.message || 'Connection failed. Check credentials and ensure terminal is running.',
      });
    }
    setConnecting(false);
  };

  // Test connection
  const handleTest = async () => {
    setMessage(null);
    const result = await apiFetch('/api/settings/test', { method: 'POST' });
    if (result?.connected) {
      setMessage({
        type: 'success',
        text: `Connection OK — Balance: $${result.balance?.toFixed(2)}, Open trades: ${result.open_trades}`,
      });
    } else {
      setMessage({ type: 'error', text: 'Not connected to any broker' });
    }
  };

  // Quick Connect E8 Markets
  const handleQuickConnectE8 = async () => {
    if (!e8Email || !e8Password) {
      setMessage({ type: 'error', text: 'Enter your E8 Markets email and password' });
      return;
    }
    setConnecting(true);
    setMessage(null);

    // Pre-fill E8 settings
    const e8Settings = {
      ...settings,
      broker: {
        ...settings.broker,
        platform: 'matchtrader',
        matchtrader_url: '',
        matchtrader_login: e8Email,
        matchtrader_password: e8Password,
        matchtrader_partner_id: '2',
      },
    };

    // Save
    const saveResult = await apiFetch('/api/settings', {
      method: 'PUT',
      body: JSON.stringify(e8Settings),
    });

    if (!saveResult?.status) {
      setMessage({ type: 'error', text: 'Failed to save E8 settings' });
      setConnecting(false);
      return;
    }

    // Connect
    const result = await apiFetch('/api/settings/connect', { method: 'POST' });
    if (result?.connected) {
      setMessage({
        type: 'success',
        text: `✓ E8 Markets connected — Balance: $${result.balance?.toFixed(2)}, Equity: $${result.equity?.toFixed(2)}`,
      });
      setE8QuickMode(false);
      await loadSettings(); // refresh displayed settings
    } else {
      setMessage({
        type: 'error',
        text: result?.message || 'E8 connection failed. Check email & password.',
      });
    }
    setConnecting(false);
  };

  // Add a prop firm account to the multi-account system
  const handleAddPropAccount = async (firmType, firmLabel) => {
    const { login, password, server, mt5_path } = propFirmCreds;
    if (!login || !password) {
      setMessage({ type: 'error', text: `Enter your ${firmLabel} login and password` });
      return;
    }
    setConnecting(true);
    setMessage(null);

    const accountId = `${firmType}_${Date.now()}`;
    const symbols = firmType === 'APEX'
      ? ['EURUSD', 'GBPUSD', 'US100', 'USDJPY']
      : ['EURUSD', 'GBPUSD', 'USDJPY'];

    const result = await apiFetch('/api/multi/account', {
      method: 'POST',
      body: JSON.stringify({
        account_id: accountId,
        firm_type: firmType,
        login: parseInt(login) || 0,
        password,
        server: server || '',
        mt5_path: mt5_path || '',
        enabled: true,
        symbols,
      }),
    });

    if (result?.status === 'OK') {
      setMessage({
        type: 'success',
        text: `✓ ${firmLabel} account added (${result.account_id}). Configure MT5 connection on a Windows PC to go live.`,
      });
      setPropFirmMode(null);
      setPropFirmCreds({ login: '', password: '', server: '', mt5_path: '' });
    } else {
      setMessage({
        type: 'error',
        text: result?.message || `Failed to add ${firmLabel} account.`,
      });
    }
    setConnecting(false);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="bg-forexia-panel border border-forexia-border rounded-xl w-full max-w-3xl max-h-[90vh] overflow-y-auto shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-forexia-border">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-widest text-white">Settings</h2>
            <p className="text-[10px] text-gray-500 mt-1">Configure broker, risk management, and agent behavior</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-white text-lg transition-colors px-2"
          >
            ✕
          </button>
        </div>

        {loading || !settings ? (
          <div className="p-12 text-center">
            <div className="w-8 h-8 border-2 border-forexia-accent border-t-transparent rounded-full animate-spin mx-auto mb-2" />
            <p className="text-xs text-gray-500">Loading settings...</p>
          </div>
        ) : (
          <div className="p-6">
            {/* Message */}
            {message && (
              <div
                className={`mb-4 px-4 py-2 rounded text-xs font-mono ${
                  message.type === 'success'
                    ? 'bg-forexia-green/10 text-forexia-green border border-forexia-green/20'
                    : 'bg-forexia-red/10 text-forexia-red border border-forexia-red/20'
                }`}
              >
                {message.text}
              </div>
            )}

            <div className="grid grid-cols-2 gap-8">
              {/* ─── LEFT COLUMN: Broker Settings ─── */}
              <div>
                <SectionHeader
                  title="Broker Connection"
                  subtitle="Configure your MT4 or MT5 trading account"
                />

                {/* ── Quick Connect E8 Markets ── */}
                {!e8QuickMode ? (
                  <button
                    onClick={() => setE8QuickMode(true)}
                    className="w-full mb-4 px-4 py-3 rounded-lg border-2 border-dashed border-forexia-accent/40 bg-forexia-accent/5 hover:bg-forexia-accent/10 hover:border-forexia-accent/70 transition-all group"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-xl">⚡</span>
                      <div className="text-left">
                        <span className="block text-[11px] font-bold text-forexia-accent uppercase tracking-wider group-hover:text-white transition-colors">
                          Quick Connect — E8 Markets
                        </span>
                        <span className="block text-[9px] text-gray-500 mt-0.5">
                          Pre-configured for E8 • Just enter email & password
                        </span>
                      </div>
                    </div>
                  </button>
                ) : (
                  <div className="mb-4 p-4 rounded-lg border border-forexia-accent/30 bg-forexia-accent/5">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <span className="text-lg">⚡</span>
                        <span className="text-[11px] font-bold text-forexia-accent uppercase tracking-wider">
                          E8 Markets — Quick Connect
                        </span>
                      </div>
                      <button
                        onClick={() => setE8QuickMode(false)}
                        className="text-gray-500 hover:text-white text-xs px-1 transition-colors"
                      >✕</button>
                    </div>
                    <p className="text-[9px] text-gray-400 mb-3">
                      URL: mtr.e8markets.com • Partner ID: 2 (pre-filled)
                    </p>
                    <Field
                      label="E8 Email"
                      value={e8Email}
                      onChange={setE8Email}
                      placeholder="your@email.com"
                    />
                    <Field
                      label="E8 Password"
                      type="password"
                      value={e8Password}
                      onChange={setE8Password}
                      placeholder="Your E8 Markets password"
                    />
                    <button
                      onClick={handleQuickConnectE8}
                      disabled={connecting || !e8Email || !e8Password}
                      className="w-full mt-1 bg-forexia-accent text-white rounded px-4 py-2.5 text-[11px] font-bold uppercase tracking-wider hover:bg-forexia-accent/80 transition-colors disabled:opacity-40 flex items-center justify-center gap-2"
                    >
                      {connecting ? (
                        <><span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> Connecting...</>
                      ) : (
                        <><span>⚡</span> Connect to E8 Markets</>
                      )}
                    </button>
                  </div>
                )}

                {/* ── Other Prop Firms: APEX, GetLeveraged, DNA Funded ── */}
                <div className="mb-4">
                  <p className="text-[9px] text-gray-500 uppercase tracking-wider mb-2 text-center">Add Prop Firm Accounts</p>
                  <div className="grid grid-cols-3 gap-2 mb-2">
                    {[
                      { key: 'APEX', label: 'APEX', icon: '🔺', color: 'text-orange-400 border-orange-400/30 bg-orange-400/5 hover:bg-orange-400/10 hover:border-orange-400/60' },
                      { key: 'GET_LEVERAGED', label: 'GetLeveraged', icon: '📈', color: 'text-blue-400 border-blue-400/30 bg-blue-400/5 hover:bg-blue-400/10 hover:border-blue-400/60' },
                      { key: 'DNA_FUNDED', label: 'DNA Funded', icon: '🧬', color: 'text-purple-400 border-purple-400/30 bg-purple-400/5 hover:bg-purple-400/10 hover:border-purple-400/60' },
                    ].map(({ key, label, icon, color }) => (
                      <button
                        key={key}
                        onClick={() => {
                          setPropFirmMode(propFirmMode === key ? null : key);
                          setPropFirmCreds({ login: '', password: '', server: '', mt5_path: '' });
                        }}
                        className={`px-2 py-2.5 rounded-lg border-2 border-dashed transition-all text-center ${
                          propFirmMode === key ? color.replace('dashed', 'solid') : color
                        }`}
                      >
                        <span className="block text-base">{icon}</span>
                        <span className="block text-[9px] font-bold uppercase tracking-wider mt-0.5">{label}</span>
                      </button>
                    ))}
                  </div>

                  {propFirmMode && (
                    <div className="p-4 rounded-lg border border-gray-600/40 bg-gray-900/60 mb-2">
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-[11px] font-bold text-white uppercase tracking-wider">
                          {propFirmMode === 'APEX' ? '🔺 APEX' : propFirmMode === 'GET_LEVERAGED' ? '📈 GetLeveraged' : '🧬 DNA Funded'} — Setup
                        </span>
                        <button onClick={() => setPropFirmMode(null)} className="text-gray-500 hover:text-white text-xs px-1 transition-colors">✕</button>
                      </div>
                      <div className="mb-2 px-3 py-2 rounded bg-yellow-500/5 border border-yellow-500/20">
                        <p className="text-[9px] text-yellow-400 leading-relaxed">
                          ⚠ <strong>Requires MT5 on Windows.</strong> These firms use MT5 terminals. Run the Forexia agent on a Windows PC with MT5 installed, or use Remote MT5 Server from macOS.
                        </p>
                      </div>
                      <Field
                        label="MT5 Account Login"
                        type="number"
                        value={propFirmCreds.login}
                        onChange={(v) => setPropFirmCreds(c => ({ ...c, login: v }))}
                        placeholder="12345678"
                        description="Your prop firm MT5 account number"
                      />
                      <Field
                        label="Password"
                        type="password"
                        value={propFirmCreds.password}
                        onChange={(v) => setPropFirmCreds(c => ({ ...c, password: v }))}
                        placeholder="MT5 trading password"
                      />
                      <Field
                        label="Server"
                        value={propFirmCreds.server}
                        onChange={(v) => setPropFirmCreds(c => ({ ...c, server: v }))}
                        placeholder={propFirmMode === 'APEX' ? 'e.g. ApexTrader-Live' : 'MT5 server name'}
                        description="Broker server name from your MT5 terminal"
                      />
                      <Field
                        label="MT5 Path (optional)"
                        value={propFirmCreds.mt5_path}
                        onChange={(v) => setPropFirmCreds(c => ({ ...c, mt5_path: v }))}
                        placeholder="C:\\Program Files\\MetaTrader 5\\terminal64.exe"
                        description="Path to the MT5 terminal — auto-detected if empty"
                      />
                      <button
                        onClick={() => handleAddPropAccount(
                          propFirmMode,
                          propFirmMode === 'APEX' ? 'APEX' : propFirmMode === 'GET_LEVERAGED' ? 'GetLeveraged' : 'DNA Funded'
                        )}
                        disabled={connecting || !propFirmCreds.login || !propFirmCreds.password}
                        className="w-full mt-1 bg-gray-700 text-white rounded px-4 py-2.5 text-[11px] font-bold uppercase tracking-wider hover:bg-gray-600 transition-colors disabled:opacity-40 flex items-center justify-center gap-2"
                      >
                        {connecting ? (
                          <><span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> Adding...</>
                        ) : (
                          <>Add {propFirmMode === 'APEX' ? 'APEX' : propFirmMode === 'GET_LEVERAGED' ? 'GetLeveraged' : 'DNA Funded'} Account</>
                        )}
                      </button>
                    </div>
                  )}
                </div>

                <div className="relative mb-4">
                  <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-gray-800"/></div>
                  <div className="relative flex justify-center"><span className="px-3 bg-forexia-panel text-[9px] text-gray-600 uppercase tracking-wider">or configure manually</span></div>
                </div>

                <Select
                  label="Platform"
                  value={settings.broker.platform}
                  onChange={(v) => updateBroker('platform', v)}
                  options={[
                    { value: 'matchtrader', label: 'MatchTrader (any OS — REST API)' },
                    { value: 'remote_mt5', label: 'Remote MT5 Server (macOS/Linux/Windows)' },
                    { value: 'mt5', label: 'MetaTrader 5 (Windows only)' },
                    { value: 'mt4', label: 'MetaTrader 4 (ZeroMQ)' },
                  ]}
                  description={settings.broker.platform === 'matchtrader'
                    ? 'Direct REST API — works from any device, no Windows needed'
                    : settings.broker.platform === 'remote_mt5'
                    ? 'Cross-platform — run mt5_remote_server.py on any Windows PC'
                    : settings.broker.platform === 'mt5'
                    ? 'Native Python API — requires Windows + MT5 terminal'
                    : 'Requires ZeroMQ EA running in MT4'
                  }
                />

                {settings.broker.platform === 'matchtrader' && (
                  <>
                    <div className="mb-3 px-3 py-2 rounded bg-forexia-accent/5 border border-forexia-accent/20">
                      <p className="text-[9px] text-forexia-accent leading-relaxed">
                        ℹ <strong>Works directly from macOS/Linux — no Windows needed.</strong><br />
                        Uses the official MatchTrader Platform API. Enter your login email and password.<br />
                        Partner ID is auto-discovered if left empty (E8 Markets = 2).
                      </p>
                    </div>
                    <Field
                      label="Platform URL"
                      value={settings.broker.matchtrader_url}
                      onChange={(v) => updateBroker('matchtrader_url', v)}
                      placeholder="https://mtr.e8markets.com"
                      description="Your broker's MatchTrader URL (e.g. https://mtr.e8markets.com)"
                    />
                    <Field
                      label="Email"
                      value={settings.broker.matchtrader_login}
                      onChange={(v) => updateBroker('matchtrader_login', v)}
                      placeholder="your@email.com"
                      description="Email you use to log into the MatchTrader platform"
                    />
                    <Field
                      label="Password"
                      type="password"
                      value={mtPasswordEdited ? settings.broker.matchtrader_password : (settings.broker.matchtrader_password === '••••••••' ? '••••••••' : settings.broker.matchtrader_password)}
                      onChange={(v) => updateBroker('matchtrader_password', v)}
                      placeholder="Trading password"
                    />
                    <Field
                      label="Partner ID"
                      value={settings.broker.matchtrader_partner_id}
                      onChange={(v) => updateBroker('matchtrader_partner_id', v)}
                      placeholder="Auto-discovered (E8 Markets = 2)"
                      description="Broker ID — leave empty to auto-discover, or enter manually"
                    />
                  </>
                )}

                {settings.broker.platform === 'remote_mt5' && (
                  <>
                    <div className="mb-3 px-3 py-2 rounded bg-forexia-accent/5 border border-forexia-accent/20">
                      <p className="text-[9px] text-forexia-accent leading-relaxed">
                        ℹ <strong>Self-hosted, no third-party accounts needed.</strong><br />
                        1. Copy <code className="bg-black/30 px-1 rounded">tools/mt5_remote_server.py</code> to any Windows PC with MT5<br />
                        2. Run: <code className="bg-black/30 px-1 rounded">pip install fastapi uvicorn MetaTrader5</code><br />
                        3. Run: <code className="bg-black/30 px-1 rounded">python mt5_remote_server.py</code><br />
                        4. Enter the server URL and auth key below
                      </p>
                    </div>
                    <Field
                      label="Server URL"
                      value={settings.broker.remote_mt5_url}
                      onChange={(v) => updateBroker('remote_mt5_url', v)}
                      placeholder="http://192.168.1.10:8089"
                      description="URL of the Windows PC running mt5_remote_server.py"
                    />
                    <Field
                      label="Auth Key"
                      type="password"
                      value={settings.broker.remote_mt5_auth_key}
                      onChange={(v) => updateBroker('remote_mt5_auth_key', v)}
                      placeholder="change_me"
                      description="Must match the AUTH_KEY in mt5_remote_server.py"
                    />
                  </>
                )}

                {(settings.broker.platform === 'mt5' || settings.broker.platform === 'mt4') && (
                  <>
                    <Field
                      label="Account Login"
                      type="number"
                      value={settings.broker.login}
                      onChange={(v) => updateBroker('login', parseInt(v) || 0)}
                      placeholder="12345678"
                      description="Your broker account number"
                    />

                    <Field
                      label="Password"
                      type="password"
                      value={passwordEdited ? settings.broker.password : '••••••••'}
                      onChange={(v) => updateBroker('password', v)}
                      placeholder="Trading password"
                    />

                    <Field
                      label="Server"
                      value={settings.broker.server}
                      onChange={(v) => updateBroker('server', v)}
                      placeholder="e.g. MetaQuotes-Demo"
                      description="Broker server name (from MT terminal)"
                    />
                  </>
                )}

                {settings.broker.platform === 'mt5' && (
                  <Field
                    label="MT5 Terminal Path"
                    value={settings.broker.mt5_path}
                    onChange={(v) => updateBroker('mt5_path', v)}
                    placeholder="Optional — auto-detected if empty"
                    description="Full path to terminal64.exe (Windows only)"
                  />
                )}

                {settings.broker.platform === 'mt5' && (
                  <div className="mb-3 px-3 py-2 rounded bg-forexia-gold/5 border border-forexia-gold/20">
                    <p className="text-[9px] text-forexia-gold">
                      ⚠ MT5 native API only works on Windows. On macOS/Linux, switch to Remote MT5 Server above.
                    </p>
                  </div>
                )}

                {/* Remote MT5 fallback for MT5 users on macOS */}
                {settings.broker.platform === 'mt5' && (
                  <div className="mt-2 pt-2 border-t border-gray-800">
                    <p className="text-[9px] text-gray-600 mb-2">Remote MT5 fallback (optional — used when MT5 native is unavailable):</p>
                    <Field
                      label="Remote Server URL"
                      value={settings.broker.remote_mt5_url}
                      onChange={(v) => updateBroker('remote_mt5_url', v)}
                      placeholder="http://192.168.1.10:8089"
                    />
                    <Field
                      label="Auth Key"
                      type="password"
                      value={settings.broker.remote_mt5_auth_key}
                      onChange={(v) => updateBroker('remote_mt5_auth_key', v)}
                      placeholder="change_me"
                    />
                  </div>
                )}

                {settings.broker.platform === 'mt4' && (
                  <>
                    <Field
                      label="ZeroMQ Host"
                      value={settings.broker.zmq_host}
                      onChange={(v) => updateBroker('zmq_host', v)}
                      placeholder="tcp://127.0.0.1"
                    />
                    <div className="grid grid-cols-2 gap-2">
                      <Field
                        label="Push Port"
                        type="number"
                        value={settings.broker.zmq_push_port}
                        onChange={(v) => updateBroker('zmq_push_port', parseInt(v) || 32768)}
                      />
                      <Field
                        label="Pull Port"
                        type="number"
                        value={settings.broker.zmq_pull_port}
                        onChange={(v) => updateBroker('zmq_pull_port', parseInt(v) || 32769)}
                      />
                    </div>
                  </>
                )}

                {/* Connection Buttons */}
                <div className="flex gap-2 mt-4">
                  <button
                    onClick={handleConnect}
                    disabled={connecting}
                    className="flex-1 bg-forexia-accent/20 text-forexia-accent border border-forexia-accent/30 rounded px-4 py-2 text-[10px] font-bold uppercase tracking-wider hover:bg-forexia-accent/30 transition-colors disabled:opacity-40"
                  >
                    {connecting ? 'Connecting...' : 'Save & Connect'}
                  </button>
                  <button
                    onClick={handleTest}
                    className="bg-gray-800 text-gray-300 border border-gray-700 rounded px-4 py-2 text-[10px] font-bold uppercase tracking-wider hover:bg-gray-700 transition-colors"
                  >
                    Test
                  </button>
                </div>
              </div>

              {/* ─── RIGHT COLUMN: Risk & Agent Settings ─── */}
              <div>
                {/* Risk Settings */}
                <SectionHeader
                  title="Risk Management"
                  subtitle="Position sizing and loss limits"
                />

                <div className="grid grid-cols-2 gap-2">
                  <Field
                    label="Lots per $100"
                    type="number"
                    value={settings.risk.lot_per_100_equity}
                    onChange={(v) => updateRisk('lot_per_100_equity', v)}
                    description="Lot sizing rule"
                  />
                  <Field
                    label="Max Risk %"
                    type="number"
                    value={settings.risk.max_risk_percent}
                    onChange={(v) => updateRisk('max_risk_percent', v)}
                    description="Per-trade risk cap"
                  />
                </div>

                <Field
                  label="Max Lot Size"
                  type="number"
                  value={settings.risk.max_lot_size}
                  onChange={(v) => updateRisk('max_lot_size', v)}
                  description="Absolute max lots per order (hard cap)"
                />

                <div className="grid grid-cols-2 gap-2">
                  <Field
                    label="Min R:R Ratio"
                    type="number"
                    value={settings.risk.take_profit_ratio}
                    onChange={(v) => updateRisk('take_profit_ratio', v)}
                    description="Minimum reward:risk"
                  />
                  <Field
                    label="SL Buffer (pips)"
                    type="number"
                    value={settings.risk.stop_loss_buffer_pips}
                    onChange={(v) => updateRisk('stop_loss_buffer_pips', v)}
                  />
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <Field
                    label="Max Open Trades"
                    type="number"
                    value={settings.risk.max_concurrent_trades}
                    onChange={(v) => updateRisk('max_concurrent_trades', parseInt(v) || 3)}
                  />
                  <Field
                    label="Daily Loss Limit %"
                    type="number"
                    value={settings.risk.max_daily_loss_percent}
                    onChange={(v) => updateRisk('max_daily_loss_percent', v)}
                  />
                </div>

                <Field
                  label="Max Spread (pips)"
                  type="number"
                  value={settings.risk.max_spread_pips}
                  onChange={(v) => updateRisk('max_spread_pips', v)}
                  description="Reject trades above this spread"
                />

                {/* Agent Settings */}
                <div className="mt-6">
                  <SectionHeader
                    title="Agent Behavior"
                    subtitle="Trading automation and signal control"
                  />

                  <Toggle
                    label="Auto-Trade"
                    checked={settings.agent.auto_trade}
                    onChange={(v) => updateAgent('auto_trade', v)}
                    description="Automatically execute signals above confidence threshold"
                  />

                  <Field
                    label="Min Confidence"
                    type="number"
                    value={settings.agent.min_confidence}
                    onChange={(v) => updateAgent('min_confidence', v)}
                    description="Minimum confidence score to auto-execute (0.0 - 1.0)"
                  />

                  <Select
                    label="Default Timeframe"
                    value={settings.agent.default_timeframe}
                    onChange={(v) => updateAgent('default_timeframe', v)}
                    options={[
                      { value: 'M1', label: 'M1 (1 Minute)' },
                      { value: 'M5', label: 'M5 (5 Minutes)' },
                      { value: 'M15', label: 'M15 (15 Minutes)' },
                      { value: 'M30', label: 'M30 (30 Minutes)' },
                      { value: 'H1', label: 'H1 (1 Hour)' },
                      { value: 'H4', label: 'H4 (4 Hours)' },
                    ]}
                  />

                  <Toggle
                    label="News Scraping"
                    checked={settings.agent.news_scraping_enabled}
                    onChange={(v) => updateAgent('news_scraping_enabled', v)}
                    description="Scrape ForexFactory for Red Folder events"
                  />

                  <Field
                    label="Webhook Secret"
                    value={settings.agent.webhook_secret}
                    onChange={(v) => updateAgent('webhook_secret', v)}
                    description="Authentication token for TradingView webhooks"
                  />
                </div>
              </div>

              {/* ─── Gemini AI Advisor ─── */}
              <div className="bg-forexia-panel rounded-lg border border-gray-800/60 overflow-hidden">
                <div className="px-4 py-2.5 bg-gray-900/60 border-b border-gray-800/40 flex items-center gap-2">
                  <span className="text-sm">🤖</span>
                  <h3 className="text-[10px] font-bold text-white uppercase tracking-wider">Gemini AI Advisor</h3>
                  <span className="text-[8px] text-gray-500">(Advisory Only — does not execute trades)</span>
                </div>
                <div className="p-4 space-y-4">
                  <Field
                    label="Gemini API Key"
                    value={settings.agent.gemini_api_key || ''}
                    onChange={(v) => updateAgent('gemini_api_key', v)}
                    type="password"
                    description={
                      <>
                        Google AI Studio API key. Get one free at{' '}
                        <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener noreferrer"
                          className="text-forexia-accent hover:underline">aistudio.google.com/apikey</a>
                      </>
                    }
                  />
                  <Field
                    label="Gemini Model"
                    value={settings.agent.gemini_model || 'gemini-2.0-flash'}
                    onChange={(v) => updateAgent('gemini_model', v)}
                    description="gemini-2.0-flash (fast, free) or gemini-2.5-pro (best quality)"
                  />
                </div>
              </div>
            </div>

            {/* Save Button */}
            <div className="mt-6 pt-4 border-t border-forexia-border flex items-center justify-between">
              <p className="text-[9px] text-gray-600">
                {settings.last_modified
                  ? `Last modified: ${new Date(settings.last_modified).toLocaleString()}`
                  : 'Not yet saved'}
              </p>
              <div className="flex gap-2">
                <button
                  onClick={onClose}
                  className="bg-gray-800 text-gray-300 border border-gray-700 rounded px-6 py-2 text-[10px] font-bold uppercase tracking-wider hover:bg-gray-700 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="bg-forexia-accent text-white rounded px-6 py-2 text-[10px] font-bold uppercase tracking-wider hover:bg-forexia-accent/80 transition-colors disabled:opacity-40"
                >
                  {saving ? 'Saving...' : 'Save Settings'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
