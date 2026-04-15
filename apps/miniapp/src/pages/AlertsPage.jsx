import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../lib/api';
import SectionBlock from '../components/ui/SectionBlock';
import PageHeader from '../components/ui/PageHeader';
import DataCard from '../components/ui/DataCard';
import StatusBadge from '../components/ui/StatusBadge';
import EmptyState from '../components/ui/EmptyState';
import LoadingState from '../components/ui/LoadingState';
import AppButton from '../components/ui/AppButton';
import { getTelegramContext } from '../lib/telegram';

function normalizeSymbol(raw) {
  return String(raw || '').trim().toUpperCase();
}

const ADD_ALERT_TYPES = [
  { value: 'price', label: 'price' },
  { value: 'rsi', label: 'rsi threshold' },
  { value: 'score', label: 'score threshold' },
  { value: 'price_ma20_cross', label: 'price x MA20' },
  { value: 'price_ma50_cross', label: 'price x MA50' },
  { value: 'ma20_ma50_cross', label: 'MA20 x MA50' },
  { value: 'signal', label: 'signal' },
];

const REMOVE_ALERT_TYPES = [
  'price',
  'rsi',
  'score',
  'price_ma20_cross',
  'price_ma50_cross',
  'ma20_ma50_cross',
  'signal',
  'macd',
  'ma',
  'change',
  'volume_spike',
];

function requiresThreshold(type) {
  return type === 'price' || type === 'rsi' || type === 'score';
}

function requiresSide(type) {
  return type === 'price' || type === 'rsi' || type === 'score' || type.includes('_cross');
}

function alertTypeHelper(type, side) {
  if (type === 'price') {
    return side === 'below' ? 'Price moves below your level.' : 'Price moves above your level.';
  }
  if (type === 'rsi') {
    return side === 'below' ? 'RSI below 30: possible oversold zone.' : 'RSI above 70: possible overbought zone.';
  }
  if (type === 'score') {
    return side === 'below' ? 'Score weakening below your threshold.' : 'Score strengthening above your threshold.';
  }
  if (type === 'price_ma20_cross') {
    return side === 'below' ? 'Price crossed below MA20 trend line.' : 'Price crossed above MA20 trend line.';
  }
  if (type === 'price_ma50_cross') {
    return side === 'below' ? 'Price crossed below MA50 trend line.' : 'Price crossed above MA50 trend line.';
  }
  if (type === 'ma20_ma50_cross') {
    return side === 'below' ? 'MA20 crossed below MA50 trend.' : 'MA20 crossed above MA50 trend.';
  }
  if (type === 'signal') {
    return 'Signal alert when model view changes.';
  }
  return 'Alert rule for selected condition.';
}

function flattenPriceAlerts(alerts) {
  const rows = [];
  const source = alerts || {};
  for (const [symbol, rules] of Object.entries(source)) {
    if (!rules || typeof rules !== 'object') continue;
    for (const [side, target] of Object.entries(rules)) {
      rows.push({
        symbol,
        side,
        target,
      });
    }
  }
  return rows;
}

function flattenAdvancedAlerts(advancedAlerts) {
  const rows = [];
  const source = advancedAlerts || {};
  for (const [symbol, list] of Object.entries(source)) {
    if (!Array.isArray(list)) continue;
    for (const rule of list) {
      rows.push({
        symbol,
        type: rule?.type || 'n/a',
        threshold: rule?.threshold,
        signal: rule?.signal,
        state: rule?.state,
        direction: rule?.direction,
      });
    }
  }
  return rows;
}

function CustomDropdown({
  value,
  onChange,
  options,
  ariaLabel,
  placeholder = 'Select',
  disabled = false,
}) {
  const [open, setOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const rootRef = useRef(null);

  const selectedIndex = options.findIndex((item) => item.value === value);
  const selectedOption = selectedIndex >= 0 ? options[selectedIndex] : null;

  useEffect(() => {
    const onPointerDown = (event) => {
      if (!rootRef.current?.contains(event.target)) {
        setOpen(false);
      }
    };

    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('touchstart', onPointerDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('touchstart', onPointerDown);
    };
  }, []);

  useEffect(() => {
    if (open) {
      setHighlightedIndex(selectedIndex >= 0 ? selectedIndex : 0);
    }
  }, [open, selectedIndex]);

  const handleTriggerKeyDown = (event) => {
    if (disabled) return;

    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }

      const step = event.key === 'ArrowDown' ? 1 : -1;
      const next = Math.max(0, Math.min(options.length - 1, highlightedIndex + step));
      setHighlightedIndex(next);
      return;
    }

    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }

      if (highlightedIndex >= 0 && highlightedIndex < options.length) {
        onChange(options[highlightedIndex].value);
        setOpen(false);
      }
      return;
    }

    if (event.key === 'Escape') {
      setOpen(false);
    }
  };

  return (
    <div className={`ds-dropdown${open ? ' is-open' : ''}${disabled ? ' is-disabled' : ''}`} ref={rootRef}>
      <button
        type="button"
        className="ds-dropdown-trigger"
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => !disabled && setOpen((prev) => !prev)}
        onKeyDown={handleTriggerKeyDown}
        disabled={disabled}
      >
        <span className="ds-dropdown-value">{selectedOption?.label || placeholder}</span>
        <span className="ds-dropdown-caret" aria-hidden="true" />
      </button>

      {open && (
        <div className="ds-dropdown-panel" role="listbox" aria-label={ariaLabel}>
          {options.map((option, index) => {
            const isSelected = option.value === value;
            const isHighlighted = index === highlightedIndex;

            return (
              <button
                key={option.value}
                type="button"
                role="option"
                aria-selected={isSelected}
                className={`ds-dropdown-option${isSelected ? ' is-selected' : ''}${isHighlighted ? ' is-highlighted' : ''}`}
                onMouseEnter={() => setHighlightedIndex(index)}
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                }}
              >
                {option.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function AlertsPage() {
  const telegramUserId = useMemo(() => {
    const ctx = getTelegramContext();
    return ctx?.user?.id ? String(ctx.user.id) : '';
  }, []);

  const [userId, setUserId] = useState(telegramUserId);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [alertsData, setAlertsData] = useState({ alerts: {}, advanced_alerts: {}, alert_items: [] });

  const [symbol, setSymbol] = useState('');
  const [alertType, setAlertType] = useState('price');
  const [side, setSide] = useState('above');
  const [target, setTarget] = useState('');

  const [removeSymbol, setRemoveSymbol] = useState('');
  const [removeType, setRemoveType] = useState('price');
  const [removeSide, setRemoveSide] = useState('above');

  const [actionMsg, setActionMsg] = useState('');

  const conditionOptions = useMemo(
    () => [
      { value: 'above', label: 'above' },
      { value: 'below', label: 'below' },
    ],
    []
  );

  const removeTypeOptions = useMemo(
    () => REMOVE_ALERT_TYPES.map((item) => ({ value: item, label: item })),
    []
  );

  const loadAlerts = ({ keepMessage = false } = {}) => {
    if (!userId.trim()) {
      setError('User id is required. Open from Telegram or enter user id.');
      return;
    }
    setLoading(true);
    setError('');
    if (!keepMessage) setActionMsg('');

    api
      .getAlerts(userId.trim())
      .then((res) => {
        setAlertsData(res || { alerts: {}, advanced_alerts: {}, alert_items: [] });
      })
      .catch((err) => setError(err.message || 'Failed to load alerts'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (!telegramUserId) return;
    loadAlerts({ keepMessage: true });
    // Run only once on first page open when Telegram user id is available.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [telegramUserId]);

  const addAlert = (e) => {
    e.preventDefault();
    if (!userId.trim()) {
      setError('User id is required.');
      return;
    }
    const normalizedSymbol = normalizeSymbol(symbol);
    if (!normalizedSymbol) {
      setError('Symbol is required.');
      return;
    }

    const payload = {
      symbol: normalizedSymbol,
      alert_type: alertType,
      side: requiresSide(alertType) ? side : undefined,
      target: requiresThreshold(alertType) && target !== '' ? Number(target) : undefined,
      threshold: requiresThreshold(alertType) && target !== '' ? Number(target) : undefined,
    };

    setLoading(true);
    setError('');
    setActionMsg('');

    api
      .addAlert(userId.trim(), payload)
      .then((res) => {
        setActionMsg(res?.message || 'Alert added');
        loadAlerts({ keepMessage: true });
      })
      .catch((err) => {
        setLoading(false);
        setError(err.message || 'Failed to add alert');
      });
  };

  const removeAlert = (e) => {
    e.preventDefault();
    if (!userId.trim()) {
      setError('User id is required.');
      return;
    }
    const normalizedSymbol = normalizeSymbol(removeSymbol);
    if (!normalizedSymbol) {
      setError('Symbol is required to remove alert.');
      return;
    }

    const payload = {
      symbol: normalizedSymbol,
      alert_type: removeType,
      side: requiresSide(removeType) ? removeSide : undefined,
    };

    setLoading(true);
    setError('');
    setActionMsg('');

    api
      .removeAlert(userId.trim(), payload)
      .then((res) => {
        setActionMsg(res?.message || 'Alert removed');
        loadAlerts({ keepMessage: true });
      })
      .catch((err) => {
        setLoading(false);
        setError(err.message || 'Failed to remove alert');
      });
  };

  const priceRows = flattenPriceAlerts(alertsData.alerts);
  const advancedRows = flattenAdvancedAlerts(alertsData.advanced_alerts);
  const normalizedItems = Array.isArray(alertsData.alert_items) ? alertsData.alert_items : [];

  const feedbackTone = error ? 'negative' : actionMsg ? 'positive' : 'neutral';

  return (
    <SectionBlock
      title="Alerts"
      subtitle="Manage user-scoped price and advanced alerts"
      className="dash-pro app-theme-finance"
    >
      <div className="ds-layout">
        <PageHeader
          title="Alerts"
          subtitle="Manage price and advanced alert rules"
          meta={`Price: ${priceRows.length} • Advanced: ${advancedRows.length}`}
        />

        <DataCard title="Alert Source" subtitle="Load alerts by Telegram user id">
          <div className="ds-alerts-source-row">
            <label className="ds-alerts-field ds-alerts-field-grow">
              <span>User ID</span>
              <input
                type="text"
                placeholder="Telegram user id"
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
              />
            </label>
            <AppButton onClick={loadAlerts} disabled={loading}>
              {loading ? 'Loading...' : 'Load Alerts'}
            </AppButton>
          </div>
        </DataCard>

        {(error || actionMsg) && (
          <DataCard title="Feedback" subtitle="Latest alert operation status">
            <StatusBadge tone={feedbackTone}>{error || actionMsg}</StatusBadge>
          </DataCard>
        )}

        {loading && <LoadingState count={2} />}

        <div className="ds-alerts-grid">
          <DataCard title="Add Alert" subtitle="Create a new monitoring rule" className="ds-market-card">
            <form onSubmit={addAlert} className="ds-alerts-form">
              <label className="ds-alerts-field">
                <span>Symbol</span>
                <input
                  type="text"
                  placeholder="THYAO"
                  value={symbol}
                  onChange={(e) => setSymbol(normalizeSymbol(e.target.value))}
                />
              </label>

              <label className="ds-alerts-field">
                <span>Alert Type</span>
                <CustomDropdown
                  value={alertType}
                  onChange={setAlertType}
                  options={ADD_ALERT_TYPES}
                  ariaLabel="Add alert type"
                  disabled={loading}
                />
                <p className="muted" style={{ margin: '0.35rem 0 0 0' }}>{alertTypeHelper(alertType, side)}</p>
              </label>

              {(requiresSide(alertType) || requiresThreshold(alertType)) && (
                <div className="ds-alerts-field-row">
                  {requiresSide(alertType) && (
                    <label className="ds-alerts-field">
                      <span>Condition</span>
                      <CustomDropdown
                        value={side}
                        onChange={setSide}
                        options={conditionOptions}
                        ariaLabel="Add alert condition"
                        disabled={loading}
                      />
                    </label>
                  )}
                  {requiresThreshold(alertType) && (
                    <label className="ds-alerts-field">
                      <span>{alertType === 'price' ? 'Target' : 'Threshold'}</span>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        placeholder="0.00"
                        value={target}
                        onChange={(e) => setTarget(e.target.value)}
                      />
                    </label>
                  )}
                </div>
              )}

              <AppButton type="submit" disabled={loading}>Add Alert</AppButton>
            </form>
          </DataCard>

          <DataCard title="Remove Alert" subtitle="Delete an existing monitoring rule" className="ds-market-card">
            <form onSubmit={removeAlert} className="ds-alerts-form">
              <label className="ds-alerts-field">
                <span>Symbol</span>
                <input
                  type="text"
                  placeholder="THYAO"
                  value={removeSymbol}
                  onChange={(e) => setRemoveSymbol(normalizeSymbol(e.target.value))}
                />
              </label>

              <label className="ds-alerts-field">
                <span>Alert Type</span>
                <CustomDropdown
                  value={removeType}
                  onChange={setRemoveType}
                  options={removeTypeOptions}
                  ariaLabel="Remove alert type"
                  disabled={loading}
                />
              </label>

              {requiresSide(removeType) && (
                <label className="ds-alerts-field">
                  <span>Condition</span>
                  <CustomDropdown
                    value={removeSide}
                    onChange={setRemoveSide}
                    options={conditionOptions}
                    ariaLabel="Remove alert condition"
                    disabled={loading}
                  />
                </label>
              )}

              <AppButton type="submit" variant="secondary" className="ds-alerts-btn-danger" disabled={loading}>
                Remove Alert
              </AppButton>
            </form>
          </DataCard>
        </div>

        <DataCard title="Alert Results" subtitle={`Price alerts: ${priceRows.length} • Advanced alerts: ${advancedRows.length}`}>
          {priceRows.length === 0 && advancedRows.length === 0 && !loading && !error ? (
            <EmptyState title="No Alerts" message="No alerts found for this user." />
          ) : (
            <div className="ds-results-grid">
              {normalizedItems.map((item, index) => (
                <DataCard
                  key={`item-${item.symbol}-${item.alert_type}-${item.condition || 'n'}-${index}`}
                  className="ds-market-card"
                  title={<div className="ds-symbol-head"><span className="ds-symbol-main">{item.symbol}</span><span className="ds-symbol-sub">{item.alert_type}</span></div>}
                  actions={<StatusBadge tone="neutral">{item.condition || 'rule'}</StatusBadge>}
                >
                  <p className="muted" style={{ margin: 0 }}>{`${item.symbol} — ${item.summary || 'Alert rule'}`}</p>
                </DataCard>
              ))}

              {normalizedItems.length === 0 && priceRows.map((item, index) => (
                <DataCard
                  key={`${item.symbol}-${item.side}-${index}`}
                  className="ds-market-card"
                  title={<div className="ds-symbol-head"><span className="ds-symbol-main">{item.symbol}</span><span className="ds-symbol-sub">Price Alert</span></div>}
                  actions={<StatusBadge tone="neutral">{item.side}</StatusBadge>}
                >
                  <p className="muted" style={{ margin: 0 }}>
                    Target: <strong>{item.target}</strong>
                  </p>
                </DataCard>
              ))}

              {normalizedItems.length === 0 && advancedRows.map((item, index) => (
                <DataCard
                  key={`${item.symbol}-${item.type}-${index}`}
                  className="ds-market-card"
                  title={<div className="ds-symbol-head"><span className="ds-symbol-main">{item.symbol}</span><span className="ds-symbol-sub">Advanced Alert</span></div>}
                  actions={<StatusBadge tone="neutral">{item.type}</StatusBadge>}
                >
                  <p className="muted" style={{ margin: 0 }}>
                    state: {item.state || 'n/a'} • direction: {item.direction || 'n/a'} • threshold: {item.threshold ?? 'n/a'}
                  </p>
                  {item.signal && <p className="muted" style={{ margin: 0 }}>signal: {item.signal}</p>}
                </DataCard>
              ))}
            </div>
          )}
        </DataCard>
      </div>
    </SectionBlock>
  );
}
