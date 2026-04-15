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
import MiniSparkline from '../components/ui/MiniSparkline';
import { getEffectiveUserId } from '../lib/telegram';

function scoreTone(score) {
  if (typeof score !== 'number') return 'neutral';
  if (score >= 70) return 'positive';
  if (score <= 40) return 'negative';
  return 'neutral';
}

function trendTone(trend) {
  const text = String(trend || '').toLowerCase();
  if (text.includes('yükseliş') || text.includes('yukselis') || text.includes('güçlü yükseliş') || text.includes('guclu yukselis')) return 'positive';
  if (text.includes('düşüş') || text.includes('dusus') || text.includes('güçlü düşüş') || text.includes('guclu dusus')) return 'negative';
  return 'neutral';
}

export default function WatchlistPage() {
  const navigate = useNavigate();
  const telegramUserId = useMemo(() => Number(getEffectiveUserId()) || 0, []);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [chatId, setChatId] = useState(telegramUserId ? String(telegramUserId) : '');
  const [symbols, setSymbols] = useState([]);
  const [allWatchlists, setAllWatchlists] = useState({});
  const [scoreMap, setScoreMap] = useState({});
  const [symbolMetaMap, setSymbolMetaMap] = useState({});

  const [inspectLoading, setInspectLoading] = useState(false);
  const [inspectError, setInspectError] = useState('');
  const [inspectData, setInspectData] = useState(null);

  const fetchScores = (symbolList) => {
    if (!symbolList.length) {
      setScoreMap({});
      return;
    }

    Promise.allSettled(symbolList.slice(0, 20).map((symbol) => api.getScore(symbol)))
      .then((results) => {
        const next = {};
        for (let i = 0; i < results.length; i += 1) {
          const res = results[i];
          const symbol = symbolList[i];
          if (res.status === 'fulfilled' && res.value) {
            next[symbol] = {
              score: res.value.score,
              trend: res.value.trend,
              strength: res.value.strength,
            };
          }
        }
        setScoreMap(next);
      })
      .catch(() => {
        setScoreMap({});
      });
  };

  const fetchSymbolMeta = (symbolList) => {
    if (!symbolList.length) {
      setSymbolMetaMap({});
      return;
    }

    Promise.allSettled(
      symbolList.slice(0, 12).map((symbol) =>
        Promise.allSettled([
          api.getSymbol(symbol),
          api.getSymbolChartSeries(symbol, { period: '1mo', limit: 30 }),
        ]).then(([quoteRes, chartRes]) => ({
          symbol,
          quote: quoteRes.status === 'fulfilled' ? quoteRes.value : null,
          points: chartRes.status === 'fulfilled' && Array.isArray(chartRes.value?.points) ? chartRes.value.points : [],
        }))
      )
    )
      .then((results) => {
        const next = {};
        results.forEach((res) => {
          if (res.status !== 'fulfilled' || !res.value?.symbol) return;
          next[res.value.symbol] = {
            quote: res.value.quote,
            points: res.value.points,
          };
        });
        setSymbolMetaMap(next);
      })
      .catch(() => {
        setSymbolMetaMap({});
      });
  };

  const formatPrice = (value) => {
    const num = Number(value);
    if (!Number.isFinite(num)) return 'n/a';
    return num.toFixed(2);
  };

  const formatChange = (value) => {
    const num = Number(value);
    if (!Number.isFinite(num)) return 'n/a';
    return `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`;
  };

  const changeTone = (value) => {
    const num = Number(value);
    if (!Number.isFinite(num) || num === 0) return 'neutral';
    return num > 0 ? 'positive' : 'negative';
  };

  const loadWatchlist = (id) => {
    setLoading(true);
    setError('');
    setInspectData(null);
    setInspectError('');
    setScoreMap({});
    setSymbolMetaMap({});
    api
      .getWatchlist(id || undefined)
      .then((res) => {
        if (id) {
          const loadedSymbols = res.symbols || [];
          setSymbols(loadedSymbols);
          setAllWatchlists({});
          fetchScores(loadedSymbols);
          fetchSymbolMeta(loadedSymbols);
        } else {
          setSymbols([]);
          setAllWatchlists(res.watchlists || {});
        }
      })
      .catch((err) => setError(err.message || 'Failed to load watchlist'))
      .finally(() => setLoading(false));
  };

  const inspectSymbol = (symbol) => {
    setInspectLoading(true);
    setInspectError('');
    setInspectData(null);

    Promise.all([api.getScore(symbol), api.getAnalysis(symbol)])
      .then(([score, analysis]) => {
        setInspectData({
          symbol,
          score,
          analysis,
        });
      })
      .catch((err) => setInspectError(err.message || 'Failed to inspect symbol'))
      .finally(() => setInspectLoading(false));
  };

  const removeSymbol = (symbol) => {
    const targetUserId = (chatId.trim() || telegramUserId).trim();
    if (!targetUserId) {
      setError('User id is required.');
      return;
    }

    setLoading(true);
    setError('');
    api
      .removeWatchlistItem({ user_id: Number(targetUserId), symbol })
      .then(() => loadWatchlist(targetUserId))
      .catch((err) => {
        setError(err.message || 'Failed to remove symbol from watchlist');
        setLoading(false);
      });
  };

  useEffect(() => {
    loadWatchlist(chatId.trim() || telegramUserId || undefined);
  }, []);

  return (
    <SectionBlock
      title="Watchlist"
      subtitle="Track symbols, scores, and inspect quickly"
      className="dash-pro app-theme-finance"
    >
      <div className="ds-layout">
        <PageHeader
          title="Watchlist"
          subtitle="Track, analyze, and manage saved symbols"
          meta={`Symbols: ${symbols.length}`}
        />

        <DataCard title="Watchlist Source" subtitle="Load by Telegram user id (optional)">
          <form
            className="input-row app-controls-row"
            onSubmit={(e) => {
              e.preventDefault();
              loadWatchlist(chatId.trim());
            }}
          >
            <input
              type="text"
              placeholder="Optional chat_id"
              value={chatId}
              onChange={(e) => setChatId(e.target.value)}
            />
            <AppButton type="submit">Load</AppButton>
          </form>
        </DataCard>

        {loading && <LoadingState count={4} />}

        {!loading && error && (
          <EmptyState title="Watchlist Error" message={error} action={<AppButton onClick={() => loadWatchlist(chatId.trim())}>Retry</AppButton>} />
        )}

        {!loading && !error && symbols.length > 0 && (
          <>
            <div className="ds-stat-grid">
              <StatCard label="Symbols" value={symbols.length} helper="Current watchlist size" />
              <StatCard label="Scored" value={Object.keys(scoreMap).length} helper="Symbols with fetched score" />
            </div>

            <div className="ds-results-grid">
              {symbols.map((symbol) => {
                const scoreInfo = scoreMap[symbol];
                const symbolMeta = symbolMetaMap[symbol];
                const changeValue = symbolMeta?.quote?.change_pct;
                return (
                  <DataCard
                    key={symbol}
                    className="ds-market-card"
                    title={(
                      <div className="ds-symbol-head">
                        <span className="ds-symbol-main">{symbol}</span>
                        <span className="ds-symbol-sub">{scoreInfo?.strength || 'No strength data yet'}</span>
                      </div>
                    )}
                    actions={<SignalBadge tone={scoreInfo ? scoreTone(scoreInfo.score) : 'neutral'}>Score {scoreInfo?.score ?? 'n/a'}</SignalBadge>}
                  >
                    <div className="ds-quote-row">
                      <div className="ds-quote-kv">
                        <small>Price</small>
                        <strong>{formatPrice(symbolMeta?.quote?.price)}</strong>
                      </div>
                      <div className="ds-quote-kv ds-quote-change">
                        <small>Change</small>
                        <SignalBadge tone={changeTone(changeValue)}>{formatChange(changeValue)}</SignalBadge>
                      </div>
                      <div className="ds-market-spark-wrap">
                        <MiniSparkline points={symbolMeta?.points || []} />
                      </div>
                    </div>

                    <div className="ds-row" style={{ marginTop: 2 }}>
                      <SignalBadge tone={trendTone(scoreInfo?.trend)}>{scoreInfo?.trend || 'Trend n/a'}</SignalBadge>
                      <SignalBadge tone="neutral">Strength {scoreInfo?.strength || 'n/a'}</SignalBadge>
                    </div>

                    <div className="ds-actions" style={{ marginTop: 10 }}>
                      <AppButton variant="secondary" onClick={() => inspectSymbol(symbol)}>Analyze</AppButton>
                      <AppButton variant="ghost" onClick={() => navigate(`/symbol/${encodeURIComponent(symbol)}`)}>Details</AppButton>
                      <AppButton onClick={() => removeSymbol(symbol)}>Remove</AppButton>
                    </div>
                  </DataCard>
                );
              })}
            </div>
          </>
        )}

        {!loading && !error && symbols.length === 0 && Object.keys(allWatchlists).length > 0 && (
          <div className="ds-results-grid">
            {Object.entries(allWatchlists).map(([id, list]) => (
              <DataCard
                key={id}
                title={`Chat ${id}`}
                subtitle={`${list.length} symbols`}
                actions={<SignalBadge tone="neutral">Shared</SignalBadge>}
              >
                <p style={{ marginBottom: 0 }}>{list.join(', ')}</p>
              </DataCard>
            ))}
          </div>
        )}

        {!loading && !error && symbols.length === 0 && Object.keys(allWatchlists).length === 0 && (
          <EmptyState title="No Watchlist Data" message="No watchlist data found." />
        )}

        {(inspectLoading || inspectError || inspectData) && (
          <DataCard title="Symbol Insight" subtitle={inspectData?.symbol || 'Selected symbol'}>
            {inspectLoading && <p className="muted">Inspecting symbol...</p>}
            {!inspectLoading && inspectError && <p className="muted">{inspectError}</p>}

            {!inspectLoading && !inspectError && inspectData && (
              <ul className="list">
                <li>
                  <strong>{inspectData.symbol}</strong>
                </li>
                <li>Score: {inspectData.score?.score ?? 'n/a'} / 100</li>
                <li>Trend: {inspectData.analysis?.trend || 'n/a'}</li>
                <li>RSI: {inspectData.analysis?.rsi ?? 'n/a'}</li>
                <li>Signal: {inspectData.analysis?.signal_summary || 'n/a'}</li>
              </ul>
            )}
          </DataCard>
        )}
      </div>
    </SectionBlock>
  );
}
