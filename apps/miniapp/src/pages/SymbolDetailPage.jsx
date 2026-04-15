import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '../lib/api';
import TradingPriceChart from '../components/charts/TradingPriceChart';
import SectionBlock from '../components/ui/SectionBlock';
import PageHeader from '../components/ui/PageHeader';
import StatCard from '../components/ui/StatCard';
import DataCard from '../components/ui/DataCard';
import SignalBadge from '../components/ui/SignalBadge';
import EmptyState from '../components/ui/EmptyState';
import LoadingState from '../components/ui/LoadingState';
import AppButton from '../components/ui/AppButton';
import { getEffectiveUserId } from '../lib/telegram';

const CHART_TIMEFRAMES = [
  { label: '1M', value: '1mo' },
  { label: '3M', value: '3mo' },
  { label: '6M', value: '6mo' },
  { label: '1Y', value: '1y' },
];

const PRICE_MODES = [
  { label: 'Candles', value: 'candles' },
  { label: 'Line', value: 'line' },
];

function normalizeSymbolInput(raw) {
  return String(raw || '').trim().toUpperCase();
}

function trendTone(trend) {
  const text = String(trend || '').toLowerCase();
  if (text.includes('yükseliş') || text.includes('yukselis')) return 'positive';
  if (text.includes('düşüş') || text.includes('dusus')) return 'negative';
  return 'neutral';
}

function scoreTone(score) {
  if (typeof score !== 'number') return 'neutral';
  if (score >= 70) return 'positive';
  if (score <= 40) return 'negative';
  return 'neutral';
}

function shortCommentary(score, analysis) {
  if (!score || !analysis) return 'Yeterli veri yok. Sembolü yeniden analiz etmeyi dene.';

  const commentary = String(analysis.commentary || '').trim();
  if (commentary) {
    return commentary;
  }

  const scoreValue = score.score;
  const trend = analysis.trend || 'Trend belirsiz';
  const rsi = analysis.rsi;
  const rsiText = typeof rsi === 'number' ? `RSI ${rsi.toFixed(2)}` : 'RSI n/a';

  if (scoreValue >= 70) {
    return `${trend} görünümü baskın. ${rsiText} ile momentum destekleniyor olabilir.`;
  }
  if (scoreValue <= 40) {
    return `${trend} tarafında baskı var. ${rsiText} ile risk yönetimi öne çıkmalı.`;
  }
  return `${trend} ve ${rsiText}. Net kırılım beklemek daha sağlıklı olabilir.`;
}

function metric(value, digits = 2) {
  if (typeof value !== 'number' || Number.isNaN(value)) return 'n/a';
  return value.toFixed(digits);
}

function metricOrReason(value, reason, digits = 2) {
  if (typeof value === 'number' && !Number.isNaN(value)) return value.toFixed(digits);
  return reason || 'Veri yetersiz';
}

function shortDate(isoDate) {
  if (!isoDate || typeof isoDate !== 'string') return '';
  const [year, month, day] = isoDate.split('-');
  if (!year || !month || !day) return isoDate;
  return `${day}.${month}`;
}

function num(value, digits = 2) {
  if (typeof value !== 'number' || Number.isNaN(value)) return 'n/a';
  return value.toFixed(digits);
}

function compactNum(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) return 'n/a';
  if (Math.abs(value) < 1000) return value.toFixed(0);

  try {
    return new Intl.NumberFormat('en', {
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(value);
  } catch {
    return value.toExponential(1);
  }
}

function volumeColor(row, index, rows, mode) {
  if (mode === 'candles') {
    const open = typeof row?.open === 'number' ? row.open : row?.close;
    const close = typeof row?.close === 'number' ? row.close : null;
    if (typeof close !== 'number' || typeof open !== 'number') return '#5d7698';
    return close >= open ? '#62c7a6' : '#df7a93';
  }

  const close = typeof row?.close === 'number' ? row.close : null;
  const prevClose = typeof rows?.[index - 1]?.close === 'number' ? rows[index - 1].close : null;
  if (typeof close !== 'number' || typeof prevClose !== 'number') return '#5d7698';
  return close >= prevClose ? '#62c7a6' : '#df7a93';
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !Array.isArray(payload) || payload.length === 0) return null;

  const dateLabel = shortDate(label);
  const entries = payload.filter((item) => item && item.value != null);
  if (entries.length === 0) return null;

  return (
    <div className="ds-chart-tooltip">
      <p>{dateLabel || label}</p>
      {entries.map((entry) => (
        <div key={entry.dataKey} className="ds-chart-tooltip-row">
          <span className="dot" style={{ backgroundColor: entry.color }} />
          <span>{entry.name}</span>
          <strong>
            {entry.dataKey === 'volume'
              ? compactNum(Number(entry.value))
              : num(Number(entry.value), entry.dataKey === 'rsi' ? 1 : 2)}
          </strong>
        </div>
      ))}
    </div>
  );
}

export default function SymbolDetailPage() {
  const { symbol: routeSymbol } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const telegramUserId = useMemo(() => Number(getEffectiveUserId()) || 0, []);

  const [inputSymbol, setInputSymbol] = useState(normalizeSymbolInput(routeSymbol || 'THYAO'));
  const [activeSymbol, setActiveSymbol] = useState(normalizeSymbolInput(routeSymbol || 'THYAO'));
  const [buyQuantity, setBuyQuantity] = useState('');
  const [buyPrice, setBuyPrice] = useState('');
  const [sellQuantity, setSellQuantity] = useState('');
  const [sellPrice, setSellPrice] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [symbolData, setSymbolData] = useState(null);
  const [score, setScore] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [chartData, setChartData] = useState([]);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState('');
  const [chartPeriod, setChartPeriod] = useState('6mo');
  const [priceMode, setPriceMode] = useState('candles');
  const [hoveredDate, setHoveredDate] = useState('');
  const [actionLoading, setActionLoading] = useState('');
  const [actionMessage, setActionMessage] = useState('');
  const [actionError, setActionError] = useState('');

  const loadChartData = useCallback((symbol, period, cancelledRef) => {
    const targetSymbol = normalizeSymbolInput(symbol);
    if (!targetSymbol) return Promise.resolve();

    setChartLoading(true);
    setChartError('');

    return api
      .getSymbolChartSeries(targetSymbol, { period, limit: 240 })
      .then((res) => {
        if (cancelledRef?.current) return;
        setChartData(Array.isArray(res?.points) ? res.points : []);
      })
      .catch((err) => {
        if (cancelledRef?.current) return;
        setChartError(err.message || 'Chart data unavailable');
        setChartData([]);
      })
      .finally(() => {
        if (!cancelledRef?.current) setChartLoading(false);
      });
  }, []);

  const loadTimedAnalysis = useCallback((symbol, period, cancelledRef) => {
    const targetSymbol = normalizeSymbolInput(symbol);
    if (!targetSymbol) return Promise.resolve();

    setAnalysisLoading(true);
    return api
      .getAnalysis(targetSymbol, { period })
      .then((res) => {
        if (cancelledRef?.current) return;
        setAnalysis(res || null);
      })
      .catch((err) => {
        if (cancelledRef?.current) return;
        setAnalysis(null);
        setError(err.message || 'Failed to load symbol details');
      })
      .finally(() => {
        if (!cancelledRef?.current) setAnalysisLoading(false);
      });
  }, []);

  const loadSymbol = useCallback(
    (target) => {
      const symbol = normalizeSymbolInput(target);
      if (!symbol) return;

      setLoading(true);
      setError('');
      setActiveSymbol(symbol);

      Promise.all([api.getScore(symbol), api.getSymbol(symbol)])
        .then(([scoreRes, symbolRes]) => {
          setScore(scoreRes);
          setSymbolData(symbolRes);
        })
        .catch((err) => {
          setError(err.message || 'Failed to load symbol details');
          setSymbolData(null);
          setScore(null);
          setAnalysis(null);
        })
        .finally(() => setLoading(false));
    },
    []
  );

  const refreshPortfolio = useCallback(() => {
    if (!telegramUserId) return;
    api.getPortfolio(telegramUserId).catch(() => {});
  }, [telegramUserId]);

  const submitTrade = useCallback(
    (side) => {
      const quantityRaw = side === 'buy' ? buyQuantity : sellQuantity;
      const priceRaw = side === 'buy' ? buyPrice : sellPrice;
      const quantity = Number(quantityRaw);
      const price = Number(priceRaw);

      if (!telegramUserId) {
        setActionError('Telegram user id not found. Open this page inside Telegram Mini App.');
        return;
      }
      if (!activeSymbol) {
        setActionError('Symbol is required.');
        return;
      }
      if (!Number.isFinite(quantity) || quantity <= 0) {
        setActionError('Quantity must be greater than 0.');
        return;
      }
      if (!Number.isFinite(price) || price <= 0) {
        setActionError('Price must be greater than 0.');
        return;
      }

      setActionLoading(side);
      setActionError('');
      setActionMessage('');

      const request = {
        user_id: telegramUserId,
        symbol: activeSymbol,
        quantity,
        price,
      };

      const call = side === 'buy' ? api.buyPortfolio(request) : api.sellPortfolio(request);

      call
        .then((res) => {
          setActionMessage(res?.message || `${side === 'buy' ? 'Buy' : 'Sell'} completed`);
          refreshPortfolio();
          loadSymbol(activeSymbol);
        })
        .catch((err) => setActionError(err.message || 'Failed to submit trade'))
        .finally(() => setActionLoading(''));
    },
    [activeSymbol, buyPrice, buyQuantity, loadSymbol, refreshPortfolio, sellPrice, sellQuantity, telegramUserId]
  );

  useEffect(() => {
    const normalized = normalizeSymbolInput(routeSymbol || inputSymbol || 'THYAO');
    setInputSymbol(normalized);
    loadSymbol(normalized);
  }, [routeSymbol, loadSymbol]);

  useEffect(() => {
    if (!activeSymbol) return;
    const cancelledRef = { current: false };
    setError('');
    loadTimedAnalysis(activeSymbol, chartPeriod, cancelledRef);
    return () => {
      cancelledRef.current = true;
    };
  }, [activeSymbol, chartPeriod, loadTimedAnalysis]);

  useEffect(() => {
    if (!activeSymbol) return;
    const cancelledRef = { current: false };
    loadChartData(activeSymbol, chartPeriod, cancelledRef);

    return () => {
      cancelledRef.current = true;
    };
  }, [activeSymbol, chartPeriod, loadChartData]);

  useEffect(() => {
    setHoveredDate('');
  }, [chartPeriod, activeSymbol, priceMode]);

  const commentary = useMemo(() => shortCommentary(score, analysis), [score, analysis]);

  const chartVisibility = useMemo(() => {
    const total = chartData.length;
    const countNumeric = (key) => chartData.reduce((acc, row) => (typeof row?.[key] === 'number' ? acc + 1 : acc), 0);

    const ma20Count = countNumeric('ma20');
    const ma50Count = countNumeric('ma50');
    const ma200Count = countNumeric('ma200');
    const rsiCount = countNumeric('rsi');

    return {
      showMA20: total >= 20 && ma20Count >= 2,
      showMA50: total >= 50 && ma50Count >= 2,
      showMA200: total >= 200 && ma200Count >= 2,
      showRSI: total >= 14 && rsiCount >= 2,
    };
  }, [chartData]);

  const volumeData = useMemo(() => {
    if (!Array.isArray(chartData) || chartData.length === 0) return [];

    return chartData.map((row, index, rows) => {
      const currentVolume = typeof row?.volume === 'number' && Number.isFinite(row.volume) ? row.volume : null;

      let vol20 = null;
      if (index >= 19) {
        const slice = rows.slice(index - 19, index + 1);
        const volumes = slice.map((item) => (typeof item?.volume === 'number' && Number.isFinite(item.volume) ? item.volume : null));
        if (volumes.every((value) => typeof value === 'number')) {
          const sum = volumes.reduce((acc, value) => acc + value, 0);
          vol20 = sum / 20;
        }
      }

      return {
        ...row,
        volume: currentVolume,
        vol20,
        volumeColor: volumeColor(row, index, rows, priceMode),
      };
    });
  }, [chartData, priceMode]);

  const showVol20 = useMemo(() => volumeData.filter((row) => typeof row?.vol20 === 'number').length >= 2, [volumeData]);

  const onSubmit = (e) => {
    e.preventDefault();
    loadSymbol(inputSymbol);
  };

  const goBackToScan = () => {
    if (location.state?.fromScan && typeof window !== 'undefined' && window.history.length > 1) {
      navigate(-1);
      return;
    }
    navigate('/scan');
  };

  return (
    <SectionBlock
      title="Symbol Detail"
      subtitle="Focused analysis for a single stock"
      className="dash-pro app-theme-finance"
    >
      <div className="ds-layout">
        <PageHeader
          title={activeSymbol || 'Symbol Detail'}
          subtitle="Single symbol analysis, scoring and actions"
          meta="Telegram-ready"
          actions={(
            <AppButton variant="ghost" onClick={goBackToScan}>
              Back to Scan
            </AppButton>
          )}
        />

        <DataCard title="Lookup" subtitle="Search symbol details">
          <form className="input-row app-controls-row" onSubmit={onSubmit}>
            <input
              type="text"
              value={inputSymbol}
              onChange={(e) => setInputSymbol(normalizeSymbolInput(e.target.value))}
              placeholder="THYAO"
            />
            <AppButton type="submit">Load</AppButton>
          </form>
        </DataCard>

        {loading && <LoadingState count={4} />}

        {!loading && error && (
          <EmptyState title="Load Error" message={error} action={<AppButton onClick={() => loadSymbol(activeSymbol || inputSymbol)}>Retry</AppButton>} />
        )}

        {!loading && !error && score && analysis && (
          <>
            <div className="ds-stat-grid">
              <StatCard label="Score" value={score.score ?? 'n/a'} helper={score.strength || 'n/a'} tone={scoreTone(score.score)} />
              <StatCard label="Trend" value={analysis.trend || 'n/a'} helper="Current technical direction" tone={trendTone(analysis.trend)} />
            </div>

            <div className="ds-results-grid">
              <DataCard title="Trade Actions" subtitle="Buy or sell this symbol">
                <div className="ds-layout">
                  <form
                    className="input-row app-controls-row"
                    onSubmit={(e) => {
                      e.preventDefault();
                      submitTrade('buy');
                    }}
                  >
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      placeholder="Quantity"
                      value={buyQuantity}
                      onChange={(e) => setBuyQuantity(e.target.value)}
                    />
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      placeholder="Price"
                      value={buyPrice}
                      onChange={(e) => setBuyPrice(e.target.value)}
                    />
                    <AppButton type="submit" disabled={actionLoading === 'buy'}>
                      Buy
                    </AppButton>
                  </form>

                  <form
                    className="input-row app-controls-row"
                    onSubmit={(e) => {
                      e.preventDefault();
                      submitTrade('sell');
                    }}
                  >
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      placeholder="Quantity"
                      value={sellQuantity}
                      onChange={(e) => setSellQuantity(e.target.value)}
                    />
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      placeholder="Price"
                      value={sellPrice}
                      onChange={(e) => setSellPrice(e.target.value)}
                    />
                    <AppButton type="submit" variant="secondary" disabled={actionLoading === 'sell'}>
                      Sell
                    </AppButton>
                  </form>
                </div>
                {actionMessage && <p className="muted" style={{ marginBottom: 0, marginTop: 8 }}>{actionMessage}</p>}
                {actionError && <p className="muted" style={{ marginBottom: 0, marginTop: 8 }}>{actionError}</p>}
              </DataCard>

              <DataCard
                title="Price Lookup"
                subtitle="Latest quote and summary"
                actions={<SignalBadge tone={trendTone(analysis.trend)}>{analysis.trend || 'Trend n/a'}</SignalBadge>}
              >
                <div className="ds-kv-grid">
                  <div className="ds-kv">
                    <small>Last Price</small>
                    <strong>{metric(symbolData?.price)}</strong>
                  </div>
                  <div className="ds-kv">
                    <small>Daily Change</small>
                    <strong>{metric(symbolData?.change_pct)}%</strong>
                  </div>
                </div>
                <p className="muted" style={{ marginBottom: 0, marginTop: 8 }}>
                  Summary: {symbolData?.summary || 'n/a'}
                </p>
              </DataCard>

              <DataCard title="Key Metrics" subtitle="Technical indicator snapshot">
                <div className="ds-kv-grid">
                  <div className="ds-kv">
                    <small>RSI</small>
                    <strong>{metric(analysis.rsi)}</strong>
                  </div>
                  <div className="ds-kv">
                    <small>Strength</small>
                    <strong>{score.strength || 'n/a'}</strong>
                  </div>
                  <div className="ds-kv">
                    <small>MA20 / MA50</small>
                    <strong>
                      {metricOrReason(analysis.ma20, analysis.ma_note)} / {metricOrReason(analysis.ma50, analysis.ma_note)}
                    </strong>
                  </div>
                  <div className="ds-kv">
                    <small>MA200</small>
                    <strong>{metricOrReason(analysis.ma200, analysis.ma_note)}</strong>
                  </div>
                </div>
              </DataCard>

              <DataCard title="Technical Chart" subtitle="Price, volume, moving averages, and RSI">
                <div className="ds-chart-controls">
                  <div className="ds-timeframe-row" role="tablist" aria-label="Chart timeframe">
                    {CHART_TIMEFRAMES.map((item) => (
                      <button
                        key={item.value}
                        type="button"
                        className={`ds-timeframe-btn ${chartPeriod === item.value ? 'active' : ''}`.trim()}
                        aria-selected={chartPeriod === item.value}
                        onClick={() => setChartPeriod(item.value)}
                        disabled={chartLoading && chartPeriod === item.value}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>

                  <div className="ds-timeframe-row ds-mode-row" role="tablist" aria-label="Price chart mode">
                    {PRICE_MODES.map((item) => (
                      <button
                        key={item.value}
                        type="button"
                        className={`ds-timeframe-btn ${priceMode === item.value ? 'active' : ''}`.trim()}
                        aria-selected={priceMode === item.value}
                        onClick={() => setPriceMode(item.value)}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                </div>

                {chartLoading && <LoadingState count={2} />}

                {!chartLoading && chartError && (
                  <EmptyState
                    title="Chart Unavailable"
                    message={chartError}
                    action={<AppButton onClick={() => loadChartData(activeSymbol, chartPeriod)}>Retry</AppButton>}
                  />
                )}

                {!chartLoading && !chartError && chartData.length > 0 && (
                  <div className="ds-chart-stack" key={`chart-${chartPeriod}`}>
                    <div className="ds-chart-panel ds-chart-price">
                      <TradingPriceChart
                        data={chartData}
                        mode={priceMode}
                        showMA20={chartVisibility.showMA20}
                        showMA50={chartVisibility.showMA50}
                        showMA200={chartVisibility.showMA200}
                        height={298}
                        onInspectChange={(point) => setHoveredDate(point?.date || '')}
                      />
                    </div>

                    <div className="ds-chart-panel ds-chart-volume">
                      <ResponsiveContainer width="100%" height={112}>
                        <ComposedChart syncId="symbol-chart-sync" data={volumeData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                          <CartesianGrid stroke="#324a6c" strokeDasharray="3 6" strokeOpacity={0.18} vertical={false} />
                          <XAxis dataKey="date" hide />
                          <YAxis
                            orientation="right"
                            tick={{ fill: '#9eb2cd', fontSize: 11 }}
                            tickFormatter={compactNum}
                            tickLine={false}
                            axisLine={{ stroke: '#2d415f' }}
                            width={44}
                          />
                          {!!hoveredDate && <ReferenceLine x={hoveredDate} stroke="#8eb4e5" strokeOpacity={0.28} strokeDasharray="3 5" />}
                          <Tooltip content={<ChartTooltip />} isAnimationActive={false} cursor={{ fill: 'rgba(146, 176, 220, 0.08)' }} />
                          <Bar dataKey="volume" name="Volume" radius={[2, 2, 0, 0]} maxBarSize={14}>
                            {volumeData.map((point, idx) => (
                              <Cell key={`${point.date}-${idx}`} fill={point.volumeColor} fillOpacity={0.72} />
                            ))}
                          </Bar>
                          {showVol20 && (
                            <Line
                              type="monotone"
                              dataKey="vol20"
                              name="Vol20"
                              stroke="#a9bfdc"
                              strokeOpacity={0.44}
                              strokeWidth={1}
                              strokeDasharray="4 4"
                              dot={false}
                              activeDot={false}
                              isAnimationActive={false}
                              connectNulls={false}
                            />
                          )}
                        </ComposedChart>
                      </ResponsiveContainer>
                    </div>

                    <div className="ds-chart-panel ds-chart-rsi">
                      <ResponsiveContainer width="100%" height={184}>
                        <LineChart syncId="symbol-chart-sync" data={chartData} margin={{ top: 8, right: 8, bottom: 6, left: 0 }}>
                          <CartesianGrid stroke="#324a6c" strokeDasharray="3 6" strokeOpacity={0.28} vertical={false} />
                          <XAxis
                            dataKey="date"
                            tickFormatter={shortDate}
                            tick={{ fill: '#9eb2cd', fontSize: 11 }}
                            tickLine={false}
                            axisLine={{ stroke: '#2d415f' }}
                            minTickGap={24}
                          />
                          <YAxis
                            orientation="right"
                            tick={{ fill: '#9eb2cd', fontSize: 11 }}
                            tickLine={false}
                            axisLine={{ stroke: '#2d415f' }}
                            domain={[0, 100]}
                            width={40}
                          />
                          {!!hoveredDate && <ReferenceLine x={hoveredDate} stroke="#8eb4e5" strokeOpacity={0.28} strokeDasharray="3 5" />}
                          <ReferenceArea y1={70} y2={100} fill="#9e3f56" fillOpacity={0.07} ifOverflow="extendDomain" />
                          <ReferenceArea y1={0} y2={30} fill="#2a7f62" fillOpacity={0.07} ifOverflow="extendDomain" />
                          <Tooltip content={<ChartTooltip />} isAnimationActive={false} cursor={{ stroke: '#a98df2', strokeOpacity: 0.32, strokeDasharray: '4 5', strokeWidth: 1.05 }} />
                          {chartVisibility.showRSI && (
                            <>
                              <ReferenceLine y={70} stroke="#d77f90" strokeOpacity={0.72} strokeDasharray="4 6" strokeWidth={1.05} ifOverflow="extendDomain" />
                              <ReferenceLine y={30} stroke="#72c5a6" strokeOpacity={0.72} strokeDasharray="4 6" strokeWidth={1.05} ifOverflow="extendDomain" />
                              <Line type="monotone" dataKey="rsi" name="RSI" stroke="#bda7ff" strokeWidth={1.85} strokeOpacity={0.96} dot={false} activeDot={{ r: 4, fill: '#bda7ff', stroke: '#efe7ff', strokeWidth: 1.2 }} isAnimationActive animationDuration={700} animationEasing="ease-out" connectNulls={false} />
                            </>
                          )}
                        </LineChart>
                      </ResponsiveContainer>
                      {!chartVisibility.showRSI && <p className="muted">RSI icin en az 14 veri noktasi gerekir.</p>}
                    </div>
                  </div>
                )}

                {!chartLoading && !chartError && chartData.length === 0 && (
                  <EmptyState title="No Chart Data" message="Not enough historical data to render chart." />
                )}
              </DataCard>

              <DataCard title="Short Commentary" subtitle="AI-style technical summary">
                <p>{commentary}</p>
                {analysisLoading && <p className="muted" style={{ marginTop: 8 }}>Updating commentary for {chartPeriod.toUpperCase()}...</p>}
                {analysis.ma_note && (
                  <p className="muted" style={{ marginTop: 8 }}>
                    MA notu: {analysis.ma_note}
                  </p>
                )}
                <p className="muted" style={{ marginBottom: 0 }}>
                  Signal summary: {analysis.signal_summary || 'n/a'}
                </p>
              </DataCard>

              <DataCard title="Related Actions" subtitle="Quick navigation and refresh">
                <div className="ds-actions">
                  <AppButton onClick={() => loadSymbol(activeSymbol)}>Analyze Again</AppButton>
                  <Link className="nav-link" to="/scan">
                    Open Scan
                  </Link>
                </div>
              </DataCard>
            </div>
          </>
        )}
      </div>
    </SectionBlock>
  );
}
