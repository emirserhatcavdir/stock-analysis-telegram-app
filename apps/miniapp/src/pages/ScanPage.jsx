import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import SectionBlock from '../components/ui/SectionBlock';
import PageHeader from '../components/ui/PageHeader';
import StatCard from '../components/ui/StatCard';
import DataCard from '../components/ui/DataCard';
import SignalBadge from '../components/ui/SignalBadge';
import EmptyState from '../components/ui/EmptyState';
import LoadingState from '../components/ui/LoadingState';
import AppButton from '../components/ui/AppButton';
import { getEffectiveUserId } from '../lib/telegram';

const SCAN_STATE_KEY = 'miniapp_scan_state_v1';
const SCAN_SCROLL_KEY = 'miniapp_scan_scroll_y_v1';

function trendTone(trend) {
  const text = String(trend || '').toLowerCase();
  if (text.includes('yükseliş') || text.includes('yukselis') || text.includes('güçlü yükseliş') || text.includes('guclu yukselis')) return 'positive';
  if (text.includes('düşüş') || text.includes('dusus') || text.includes('güçlü düşüş') || text.includes('guclu dusus')) return 'negative';
  return 'neutral';
}

function scoreTone(score) {
  if (typeof score !== 'number') return 'neutral';
  if (score >= 70) return 'positive';
  if (score <= 40) return 'negative';
  return 'neutral';
}

function tagTone(tag) {
  const text = String(tag || '').toLowerCase();
  if (text.includes('trend leader') || text.includes('momentum') || text.includes('breakout')) return 'positive';
  if (text.includes('weak') || text.includes('risky')) return 'negative';
  if (text.includes('oversold') || text.includes('rebound')) return 'neutral';
  return 'neutral';
}

function signalTone(signal) {
  const text = String(signal || '').toLowerCase();
  if (text.includes('buy') || text.includes('al')) return 'positive';
  if (text.includes('sell') || text.includes('sat')) return 'negative';
  return 'neutral';
}

function strengthTone(strength) {
  const text = String(strength || '').toLowerCase();
  if (text.includes('strong') || text.includes('guclu')) return 'positive';
  if (text.includes('weak') || text.includes('zayif')) return 'negative';
  return 'neutral';
}

function normalizeSymbolInput(raw) {
  return String(raw || '').trim().toUpperCase();
}

export default function ScanPage() {
  const navigate = useNavigate();

  const [filters, setFilters] = useState({
    universe: 'bist30',
    limit: 10,
    minScore: 0,
    strongBuyOnly: false,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [rows, setRows] = useState([]);
  const [selectedSymbol, setSelectedSymbol] = useState('');
  const [selectedAnalysis, setSelectedAnalysis] = useState(null);
  const [actionError, setActionError] = useState('');
  const [actionLoading, setActionLoading] = useState('');
  const [quickSymbol, setQuickSymbol] = useState('THYAO.IS');
  const [quickQuantity, setQuickQuantity] = useState('1');
  const [quickPrice, setQuickPrice] = useState('');
  const [quickLoading, setQuickLoading] = useState('');
  const [quickError, setQuickError] = useState('');
  const [quickMessage, setQuickMessage] = useState('');
  const [hasRestoredState, setHasRestoredState] = useState(false);

  const telegramUserId = useMemo(() => Number(getEffectiveUserId()) || 0, []);

  const getQuickSymbol = () => normalizeSymbolInput(quickSymbol);

  const validateQuickSymbol = () => {
    const symbol = getQuickSymbol();
    if (!symbol) {
      setQuickError('Enter a symbol first.');
      return '';
    }
    return symbol;
  };

  const clearQuickFeedback = () => {
    setQuickError('');
    setQuickMessage('');
  };

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const raw = window.sessionStorage.getItem(SCAN_STATE_KEY);
      if (raw) {
        const saved = JSON.parse(raw);
        if (saved?.filters) {
          setFilters((prev) => ({
            ...prev,
            ...saved.filters,
          }));
        }
        if (Array.isArray(saved?.rows)) setRows(saved.rows);
        if (typeof saved?.selectedSymbol === 'string') setSelectedSymbol(saved.selectedSymbol);
        if (saved?.selectedAnalysis && typeof saved.selectedAnalysis === 'object') {
          setSelectedAnalysis(saved.selectedAnalysis);
        }
      }

      const scrollRaw = window.sessionStorage.getItem(SCAN_SCROLL_KEY);
      const scrollY = Number(scrollRaw);
      if (Number.isFinite(scrollY) && scrollY > 0) {
        window.requestAnimationFrame(() => {
          window.scrollTo({ top: scrollY, behavior: 'auto' });
        });
        window.sessionStorage.removeItem(SCAN_SCROLL_KEY);
      }
    } catch {
      // Ignore storage parse errors and keep default state.
    } finally {
      // Persist only after restore pass has completed to avoid default-state overwrite.
      setHasRestoredState(true);
    }
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (!hasRestoredState) return;
    const payload = {
      filters,
      rows,
      selectedSymbol,
      selectedAnalysis,
    };
    try {
      window.sessionStorage.setItem(SCAN_STATE_KEY, JSON.stringify(payload));
    } catch {
      // Ignore storage quota issues.
    }
  }, [filters, rows, selectedSymbol, selectedAnalysis, hasRestoredState]);

  const openDetails = (symbol) => {
    if (typeof window !== 'undefined') {
      try {
        window.sessionStorage.setItem(SCAN_SCROLL_KEY, String(window.scrollY || 0));
      } catch {
        // Ignore storage issues.
      }
    }
    navigate(`/symbol/${encodeURIComponent(symbol)}`, { state: { fromScan: true } });
  };

  const runScan = () => {
    setLoading(true);
    setError('');
    setActionError('');
    setSelectedSymbol('');
    setSelectedAnalysis(null);

    api
      .getScan({
        universe: filters.universe,
        limit: filters.limit,
        min_score: filters.minScore,
        strong_buy_only: filters.strongBuyOnly,
      })
      .then((res) => {
        setRows(res?.results || []);
      })
      .catch((err) => setError(err.message || 'Scan failed'))
      .finally(() => setLoading(false));
  };

  const analyzeSymbol = (symbol) => {
    setActionLoading(symbol);
    setActionError('');
    setSelectedSymbol(symbol);
    setSelectedAnalysis(null);

    api
      .getAnalysis(symbol)
      .then((analysis) => setSelectedAnalysis(analysis))
      .catch((err) => setActionError(err.message || 'Failed to analyze symbol'))
      .finally(() => setActionLoading(''));
  };

  const quickAnalyze = () => {
    const symbol = validateQuickSymbol();
    if (!symbol) return;

    setQuickLoading('analyze');
    clearQuickFeedback();

    Promise.all([api.getAnalysis(symbol), api.getSymbol(symbol)])
      .then(([analysis, symbolData]) => {
        setSelectedSymbol(symbol);
        setSelectedAnalysis(analysis);
        setQuickMessage(`${symbol} loaded successfully.`);
        if (symbolData?.summary) {
          setQuickMessage(symbolData.summary);
        }
      })
      .catch((err) => setQuickError(err.message || 'Failed to analyze symbol'))
      .finally(() => setQuickLoading(''));
  };

  const quickOpenDetails = () => {
    const symbol = validateQuickSymbol();
    if (!symbol) return;
    openDetails(symbol);
  };

  const quickAddToWatchlist = () => {
    const symbol = validateQuickSymbol();
    if (!symbol) return;
    if (!telegramUserId) {
      setQuickError('User id not found. Open inside Telegram Mini App or set VITE_DEV_USER_ID for local dev.');
      return;
    }

    setQuickLoading('watchlist');
    clearQuickFeedback();
    api
      .addWatchlistItem({ user_id: telegramUserId, symbol })
      .then((res) => setQuickMessage(res?.message || `${symbol} added to watchlist.`))
      .catch((err) => setQuickError(err.message || 'Failed to add watchlist item'))
      .finally(() => setQuickLoading(''));
  };

  const submitQuickTrade = (side) => {
    const symbol = validateQuickSymbol();
    if (!symbol) return;

    if (!telegramUserId) {
      setQuickError('User id not found. Open inside Telegram Mini App or set VITE_DEV_USER_ID for local dev.');
      return;
    }

    const quantity = Number(quickQuantity);
    const price = Number(quickPrice);

    if (!Number.isFinite(quantity) || quantity <= 0) {
      setQuickError('Quantity must be greater than 0.');
      return;
    }

    if (!Number.isFinite(price) || price <= 0) {
      setQuickError('Price must be greater than 0.');
      return;
    }

    setQuickLoading(side);
    clearQuickFeedback();

    const request = {
      user_id: telegramUserId,
      symbol,
      quantity,
      price,
    };

    const tradeCall = side === 'buy' ? api.buyPortfolio(request) : api.sellPortfolio(request);
    tradeCall
      .then((res) => setQuickMessage(res?.message || `${side === 'buy' ? 'Buy' : 'Sell'} completed`))
      .catch((err) => setQuickError(err.message || 'Failed to submit trade'))
      .finally(() => setQuickLoading(''));
  };

  const addToWatchlist = (symbol) => {
    if (!telegramUserId) {
      setActionError('User id not found. Open inside Telegram Mini App or set VITE_DEV_USER_ID for local dev.');
      return;
    }

    setActionLoading(symbol);
    setActionError('');
    api
      .addWatchlistItem({ user_id: telegramUserId, symbol })
      .catch((err) => setActionError(err.message || 'Failed to add watchlist item'))
      .finally(() => setActionLoading(''));
  };

  return (
    <SectionBlock
      title="Scan"
      subtitle="Run ranked scans, filter results, and take quick actions"
      className="dash-pro app-theme-finance"
    >
      <div className="ds-layout">
        <PageHeader
          title="Market Scan"
          subtitle="Ranked opportunities with fast actions"
          meta={`Universe: ${filters.universe.toUpperCase()}`}
        />

        <DataCard title="Quick Symbol" subtitle="Manual actions for any stock symbol">
          <div className="ds-filter-row">
            <label className="ds-quick-symbol">
              Symbol
              <input
                type="text"
                value={quickSymbol}
                onChange={(e) => setQuickSymbol(normalizeSymbolInput(e.target.value))}
                placeholder="THYAO.IS"
              />
            </label>
            <label className="ds-quick-qty">
              Quantity
              <input
                type="number"
                min="0"
                step="1"
                value={quickQuantity}
                onChange={(e) => setQuickQuantity(e.target.value)}
                placeholder="1"
              />
            </label>
            <label className="ds-quick-price">
              Price
              <input
                type="number"
                min="0"
                step="0.01"
                value={quickPrice}
                onChange={(e) => setQuickPrice(e.target.value)}
                placeholder="0.00"
              />
            </label>
          </div>

          <div className="ds-actions">
            <AppButton onClick={quickAnalyze} disabled={quickLoading === 'analyze'}>
              {quickLoading === 'analyze' ? 'Analyzing...' : 'Analyze'}
            </AppButton>
            <AppButton variant="secondary" onClick={() => submitQuickTrade('buy')} disabled={quickLoading === 'buy'}>
              {quickLoading === 'buy' ? 'Buying...' : 'Buy'}
            </AppButton>
            <AppButton variant="secondary" onClick={() => submitQuickTrade('sell')} disabled={quickLoading === 'sell'}>
              {quickLoading === 'sell' ? 'Selling...' : 'Sell'}
            </AppButton>
            <AppButton variant="ghost" onClick={quickOpenDetails} disabled={quickLoading === 'watchlist'}>
              Open Details
            </AppButton>
            <AppButton variant="ghost" onClick={quickAddToWatchlist} disabled={quickLoading === 'watchlist'}>
              {quickLoading === 'watchlist' ? 'Adding...' : 'Add to Watchlist'}
            </AppButton>
          </div>

          {quickLoading && <LoadingState count={1} />}
          {quickError && <p className="muted" style={{ color: '#ffb0bb', marginBottom: 0 }}>{quickError}</p>}
          {quickMessage && <p className="muted" style={{ marginBottom: 0 }}>{quickMessage}</p>}
        </DataCard>

        <DataCard title="Filters" subtitle="Adjust then run scan">
          <div className="ds-filter-row">
            <label>
            Min Score
            <input
              type="number"
              min="0"
              max="100"
              value={filters.minScore}
              onChange={(e) =>
                setFilters((prev) => ({
                  ...prev,
                  minScore: Number(e.target.value) || 0,
                }))
              }
            />
            </label>

            <label className="ds-switch">
              <input
                type="checkbox"
                checked={filters.strongBuyOnly}
                onChange={(e) =>
                  setFilters((prev) => ({
                    ...prev,
                    strongBuyOnly: e.target.checked,
                  }))
                }
              />
              Strong Buy Only
            </label>

            <AppButton onClick={runScan} disabled={loading}>
              {loading ? 'Running...' : 'Run Scan'}
            </AppButton>
          </div>
        </DataCard>

        {loading && <LoadingState count={4} />}

        {!loading && error && (
          <EmptyState title="Scan Error" message={error} action={<AppButton onClick={runScan}>Try Again</AppButton>} />
        )}

        {!loading && actionError && (
          <EmptyState title="Action Error" message={actionError} />
        )}

        {!loading && rows.length > 0 && (
          <>
            <div className="ds-stat-grid">
              <StatCard label="Results" value={rows.length} helper="Matched symbols" />
              <StatCard label="Min Score" value={filters.minScore} helper={filters.strongBuyOnly ? 'Strong-buy filter on' : 'All signals'} />
            </div>

            <div className="ds-results-grid">
              {rows.map((row) => (
                <DataCard
                  key={row.symbol}
                  className="ds-market-card"
                  title={(
                    <div className="ds-symbol-head">
                      <span className="ds-symbol-main">{row.symbol}</span>
                      <span className="ds-symbol-sub">Rank #{row.rank ?? '-'}</span>
                    </div>
                  )}
                  actions={<SignalBadge tone={scoreTone(row.score)}>Score {row.score ?? 'n/a'}</SignalBadge>}
                >
                  <div className="ds-row">
                    <SignalBadge tone={signalTone(row.signal)}>{row.signal || 'Signal n/a'}</SignalBadge>
                    <SignalBadge tone={strengthTone(row.strength)}>{row.strength || 'Strength n/a'}</SignalBadge>
                    <SignalBadge tone={trendTone(row.trend)}>{row.trend || 'Trend n/a'}</SignalBadge>
                  </div>

                  <div className="ds-kv-grid">
                    <div className="ds-kv">
                      <small>RSI</small>
                      <strong>{typeof row.rsi === 'number' ? row.rsi.toFixed(2) : 'n/a'}</strong>
                    </div>
                    <div className="ds-kv">
                      <small>Score</small>
                      <strong>{typeof row.score === 'number' ? row.score.toFixed(1) : 'n/a'}</strong>
                    </div>
                  </div>

                  {Array.isArray(row.tags) && row.tags.length > 0 && (
                    <div className="ds-row" style={{ marginTop: 10 }}>
                      {row.tags.map((tag) => (
                        <SignalBadge key={tag} tone={tagTone(tag)}>
                          {tag}
                        </SignalBadge>
                      ))}
                    </div>
                  )}

                  <div className="ds-actions" style={{ marginTop: 10 }}>
                    <AppButton
                      onClick={() => analyzeSymbol(row.symbol)}
                      disabled={actionLoading === row.symbol}
                    >
                      Analyze
                    </AppButton>
                    <AppButton
                      variant="secondary"
                      onClick={() => addToWatchlist(row.symbol)}
                      disabled={actionLoading === row.symbol}
                    >
                      Add to watchlist
                    </AppButton>
                    <AppButton variant="ghost" onClick={() => openDetails(row.symbol)}>
                      Open details
                    </AppButton>
                  </div>
                </DataCard>
              ))}
            </div>

            {(selectedSymbol || selectedAnalysis) && (
              <DataCard title="Symbol Insight" subtitle={selectedSymbol || 'Selected symbol'}>
                {actionLoading === selectedSymbol && selectedSymbol && <p className="muted">Inspecting symbol...</p>}
                {selectedAnalysis && (
                  <ul className="list">
                    <li>
                      <strong>{selectedSymbol}</strong>
                    </li>
                    <li>Trend: {selectedAnalysis.trend || 'n/a'}</li>
                    <li>RSI: {selectedAnalysis.rsi ?? 'n/a'}</li>
                    <li>Signal: {selectedAnalysis.signal_summary || 'n/a'}</li>
                  </ul>
                )}
              </DataCard>
            )}
          </>
        )}

        {!loading && !error && rows.length === 0 && (
          <EmptyState title="No Results Yet" message="No scan results yet. Click Run Scan." action={<AppButton onClick={runScan}>Run Scan</AppButton>} />
        )}
      </div>
    </SectionBlock>
  );
}