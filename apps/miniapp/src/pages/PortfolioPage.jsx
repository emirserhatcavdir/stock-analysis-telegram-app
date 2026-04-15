import { useCallback, useEffect, useMemo, useState } from 'react';
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

function asNumber(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function formatMoney(value) {
  if (value === null || value === undefined || !Number.isFinite(value)) return 'n/a';
  return `${value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} TL`;
}

function formatPct(value) {
  if (!Number.isFinite(value)) return 'n/a';
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function formatSignedMoney(value) {
  if (!Number.isFinite(value)) return 'n/a';
  return `${value >= 0 ? '+' : ''}${formatMoney(value)}`;
}

function toneFromValue(value) {
  if (!Number.isFinite(value) || value === 0) return 'neutral';
  return value > 0 ? 'positive' : 'negative';
}

export default function PortfolioPage() {
  const navigate = useNavigate();
  const telegramUserId = useMemo(() => Number(getEffectiveUserId()) || 0, []);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [data, setData] = useState({ positions: {}, total_positions: 0 });
  const [insights, setInsights] = useState(null);
  const [trades, setTrades] = useState({ total_realized: 0, trades: [] });
  const [sellDialog, setSellDialog] = useState({ open: false, row: null });
  const [sellSubmitting, setSellSubmitting] = useState(false);
  const [sellError, setSellError] = useState('');

  const loadPortfolioData = useCallback(() => {
    return Promise.all([
      api.getPortfolio(telegramUserId || undefined),
      api.getPortfolioInsights(telegramUserId || undefined),
      api.getTradeHistory(telegramUserId || undefined, 20),
    ]).then(([portfolioRes, insightsRes, tradesRes]) => {
      setData(portfolioRes);
      setInsights(insightsRes);
      setTrades(tradesRes);
    });
  }, [telegramUserId]);

  useEffect(() => {
    let mounted = true;
    loadPortfolioData()
      .then(() => {
        if (!mounted) return;
      })
      .catch((err) => {
        if (mounted) setError(err.message || 'Failed to load portfolio');
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [loadPortfolioData]);

  const rows = Object.entries(data.positions || {}).map(([symbol, item]) => {
    const shares = asNumber(item.shares);
    const buyPrice = asNumber(item.buy_price);
    const value = shares * buyPrice;
    const realized = Number.isFinite(Number(item.realized_pnl)) ? Number(item.realized_pnl) : 0;
    const unrealized = Number.isFinite(Number(item.unrealized_pnl)) ? Number(item.unrealized_pnl) : null;

    return {
      symbol,
      shares,
      buyPrice,
      value,
      realized,
      unrealized,
    };
  });

  const totalValue = Number.isFinite(Number(insights?.summary?.total_value))
    ? Number(insights.summary.total_value)
    : rows.reduce((sum, row) => sum + row.value, 0);
  const totalCost = Number.isFinite(Number(insights?.summary?.total_cost))
    ? Number(insights.summary.total_cost)
    : rows.reduce((sum, row) => sum + (row.buyPrice * row.shares), 0);
  const totalRealized = Number.isFinite(Number(insights?.summary?.realized_pnl))
    ? Number(insights.summary.realized_pnl)
    : rows.reduce((sum, row) => sum + row.realized, 0);
  const hasUnrealizedData = rows.some((row) => row.unrealized !== null);
  const totalUnrealized = Number.isFinite(Number(insights?.summary?.unrealized_pnl))
    ? Number(insights.summary.unrealized_pnl)
    : (hasUnrealizedData ? rows.reduce((sum, row) => sum + (row.unrealized ?? 0), 0) : null);
  const netPnl = Number.isFinite(Number(insights?.summary?.net_pnl))
    ? Number(insights.summary.net_pnl)
    : (Number.isFinite(totalRealized) && Number.isFinite(totalUnrealized) ? totalRealized + totalUnrealized : null);

  const withAllocation = rows.map((row) => ({
    ...row,
    allocation: totalValue > 0 ? (row.value / totalValue) * 100 : 0,
  }));

  const pnlTone = toneFromValue;

  const openSellDialog = (row) => {
    setSellError('');
    setSellDialog({ open: true, row });
  };

  const closeSellDialog = () => {
    if (sellSubmitting) return;
    setSellDialog({ open: false, row: null });
    setSellError('');
  };

  const confirmSell = () => {
    const row = sellDialog.row;
    if (!row) return;

    setSellSubmitting(true);
    setSellError('');

    api
      .sellPortfolio({
        user_id: telegramUserId,
        symbol: row.symbol,
        quantity: row.shares,
        price: row.buyPrice,
      })
      .then(() => loadPortfolioData())
      .then(() => {
        setSellDialog({ open: false, row: null });
      })
      .catch((err) => {
        setSellError(err.message || 'Sell failed');
      })
      .finally(() => {
        setSellSubmitting(false);
      });
  };

  return (
    <SectionBlock
      title="Portfolio"
      subtitle="Holdings, allocation, and pnl snapshot"
      className="dash-pro app-theme-finance"
    >
      <div className="ds-layout">
        <PageHeader
          title="Portfolio Overview"
          subtitle="Holdings, performance, and trade activity"
          meta={`Positions: ${data.total_positions || 0}`}
        />

        {loading && <LoadingState count={4} />}

        {!loading && error && (
          <EmptyState title="Portfolio Error" message={error} />
        )}

        {!loading && !error && (
          <>
            <div className="ds-stat-grid">
              <StatCard label="Total Value" value={formatMoney(totalValue)} helper="Current portfolio value" />
              <StatCard label="Total Cost" value={formatMoney(totalCost)} helper="Average cost basis" />
              <StatCard label="Realized PnL" value={formatSignedMoney(totalRealized)} helper="Closed trade impact" tone={pnlTone(totalRealized)} />
              <StatCard label="Net PnL" value={formatSignedMoney(netPnl)} helper="Realized + unrealized" tone={pnlTone(netPnl)} />
            </div>

            <DataCard title="Performance" subtitle="Short-term change profile">
              <div className="ds-kv-grid ds-performance-grid">
                <div className="ds-kv ds-market-kv">
                  <small>Daily</small>
                  <strong>{formatSignedMoney(Number(insights?.performance?.daily_abs))}</strong>
                  <SignalBadge tone={toneFromValue(Number(insights?.performance?.daily_pct))}>{formatPct(Number(insights?.performance?.daily_pct))}</SignalBadge>
                </div>
                <div className="ds-kv ds-market-kv">
                  <small>Weekly</small>
                  <strong>{formatSignedMoney(Number(insights?.performance?.weekly_abs))}</strong>
                  <SignalBadge tone={toneFromValue(Number(insights?.performance?.weekly_pct))}>{formatPct(Number(insights?.performance?.weekly_pct))}</SignalBadge>
                </div>
              </div>
            </DataCard>

            <DataCard title="Winners & Losers" subtitle="Best and worst contributors">
              <div className="ds-kv-grid">
                <div>
                  <div className="muted" style={{ marginBottom: 8 }}>Top Winners</div>
                  {(insights?.winners || []).length === 0 ? (
                    <p className="muted" style={{ margin: 0 }}>No winner data</p>
                  ) : (
                    (insights.winners || []).map((item) => (
                      <div key={`w-${item.symbol}`} className="ds-row-between" style={{ marginBottom: 8 }}>
                        <span>{item.symbol}</span>
                        <SignalBadge tone="positive">{formatPct(Number(item.unrealized_pct))}</SignalBadge>
                      </div>
                    ))
                  )}
                </div>
                <div>
                  <div className="muted" style={{ marginBottom: 8 }}>Top Losers</div>
                  {(insights?.losers || []).length === 0 ? (
                    <p className="muted" style={{ margin: 0 }}>No loser data</p>
                  ) : (
                    (insights.losers || []).map((item) => (
                      <div key={`l-${item.symbol}`} className="ds-row-between" style={{ marginBottom: 8 }}>
                        <span>{item.symbol}</span>
                        <SignalBadge tone="negative">{formatPct(Number(item.unrealized_pct))}</SignalBadge>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </DataCard>

            <DataCard title="Allocation" subtitle="Weight by current value">
              {(insights?.allocation || []).length === 0 ? (
                <p className="muted" style={{ margin: 0 }}>No allocation data</p>
              ) : (
                (insights.allocation || []).map((item) => (
                  <div key={`a-${item.symbol}`} className="ds-alloc-row">
                    <div className="ds-row-between">
                      <span>{item.symbol}</span>
                      <span>{formatPct(Number(item.pct))} • {formatMoney(Number(item.value))}</span>
                    </div>
                    <div className="ds-alloc-track" role="presentation">
                      <div className="ds-alloc-fill" style={{ width: `${Math.max(0, Math.min(100, Number(item.pct) || 0))}%` }} />
                    </div>
                  </div>
                ))
              )}
            </DataCard>

            <DataCard title="Trade History" subtitle="Recent transactions">
              <p className="muted" style={{ marginTop: 0 }}>
                Total realized: {formatSignedMoney(Number(trades?.total_realized || 0))}
              </p>
              {(trades?.trades || []).length === 0 ? (
                <p className="muted" style={{ margin: 0 }}>No trades yet</p>
              ) : (
                (trades.trades || []).map((item, idx) => (
                  <div key={`${item.timestamp}-${item.symbol}-${idx}`} className="ds-row-between" style={{ marginBottom: 8 }}>
                    <span>{item.side?.toUpperCase()} {item.symbol} {Number(item.quantity).toLocaleString()}</span>
                    <span>{formatMoney(Number(item.price))} • {formatSignedMoney(Number(item.realized_pnl))}</span>
                  </div>
                ))
              )}
            </DataCard>

            {withAllocation.length === 0 ? (
              <EmptyState title="No Positions" message="No positions found. Add holdings from the bot first." />
            ) : (
              <DataCard title="Portfolio Positions" subtitle={`Active symbols: ${withAllocation.length}`}>
                <div className="ds-results-grid">
                  {withAllocation.map((row) => (
                    <DataCard
                      key={row.symbol}
                      className="ds-market-card"
                      title={(
                        <div className="ds-symbol-head">
                          <span className="ds-symbol-main">{row.symbol}</span>
                          <span className="ds-symbol-sub">Allocation {formatPct(row.allocation)}</span>
                        </div>
                      )}
                      actions={<SignalBadge tone={pnlTone(row.unrealized)}>Unrealized {formatSignedMoney(row.unrealized)}</SignalBadge>}
                    >
                      <div className="ds-kv-grid">
                        <div className="ds-kv">
                          <small>Shares</small>
                          <strong>{row.shares.toLocaleString()}</strong>
                        </div>
                        <div className="ds-kv">
                          <small>Avg Cost</small>
                          <strong>{formatMoney(row.buyPrice)}</strong>
                        </div>
                        <div className="ds-kv">
                          <small>Value</small>
                          <strong>{formatMoney(row.value)}</strong>
                        </div>
                        <div className="ds-kv">
                          <small>Realized</small>
                          <strong>{formatSignedMoney(row.realized)}</strong>
                        </div>
                        <div className="ds-kv">
                          <small>Unrealized</small>
                          <SignalBadge tone={pnlTone(row.unrealized)}>{formatSignedMoney(row.unrealized)}</SignalBadge>
                        </div>
                      </div>

                      <div className="ds-actions" style={{ marginTop: 10 }}>
                        <AppButton variant="secondary" onClick={() => openSellDialog(row)}>
                          Sell
                        </AppButton>
                        <AppButton variant="ghost" onClick={() => navigate(`/symbol/${encodeURIComponent(row.symbol)}`)}>
                          Details
                        </AppButton>
                      </div>
                    </DataCard>
                  ))}
                </div>
              </DataCard>
            )}
          </>
        )}

        {sellDialog.open && sellDialog.row && (
          <div className="ds-modal-overlay" role="dialog" aria-modal="true" aria-label="Sell confirmation">
            <div className="ds-modal-card">
              <h3>Bu urunu satmak istiyor musunuz?</h3>
              <p className="muted" style={{ marginTop: 0 }}>
                Sembol: {sellDialog.row.symbol} | Adet: {sellDialog.row.shares.toLocaleString()} | Fiyat: {formatMoney(sellDialog.row.buyPrice)}
              </p>
              {sellError && <p className="muted" style={{ color: '#ffb0bb', marginTop: 0 }}>{sellError}</p>}
              <div className="ds-actions">
                <AppButton onClick={confirmSell} disabled={sellSubmitting}>
                  {sellSubmitting ? 'Satis yapiliyor...' : 'Evet, sat'}
                </AppButton>
                <AppButton variant="ghost" onClick={closeSellDialog} disabled={sellSubmitting}>
                  Hayir
                </AppButton>
              </div>
            </div>
          </div>
        )}
      </div>
    </SectionBlock>
  );
}
