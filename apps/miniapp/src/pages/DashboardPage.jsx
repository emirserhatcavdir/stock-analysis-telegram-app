import { useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api';

function formatPct(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) return 'n/a';
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function collectScanCandidates(scan) {
  const buckets = [scan?.oversold || [], scan?.overbought || [], scan?.strong_trend || []];
  const map = new Map();
  for (const bucket of buckets) {
    for (const item of bucket) {
      if (!item?.symbol) continue;
      const prev = map.get(item.symbol);
      const currentChange = typeof item.change_pct === 'number' ? item.change_pct : null;
      const prevChange = typeof prev?.change_pct === 'number' ? prev.change_pct : null;
      if (!prev || (currentChange !== null && (prevChange === null || Math.abs(currentChange) > Math.abs(prevChange)))) {
        map.set(item.symbol, item);
      }
    }
  }
  return [...map.values()];
}

function clampScore(value) {
  if (!Number.isFinite(value)) return 0;
  if (value < 0) return 0;
  if (value > 100) return 100;
  return Math.round(value);
}

function positiveCount(rows) {
  return rows.filter((x) => typeof x.change_pct === 'number' && x.change_pct > 0).length;
}

function negativeCount(rows) {
  return rows.filter((x) => typeof x.change_pct === 'number' && x.change_pct < 0).length;
}

export default function DashboardPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [sectionErrors, setSectionErrors] = useState([]);
  const [portfolio, setPortfolio] = useState({ positions: {}, total_positions: 0 });
  const [watchlist, setWatchlist] = useState({ chat_id: null, symbols: [], watchlists: {} });
  const [scan, setScan] = useState(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError('');

    Promise.allSettled([api.getPortfolio(), api.getWatchlist(), api.getBist30Scan()])
      .then((results) => {
        if (!mounted) return;

        const nextErrors = [];

        const portfolioRes = results[0];
        if (portfolioRes.status === 'fulfilled') {
          setPortfolio(portfolioRes.value || { positions: {}, total_positions: 0 });
        } else {
          setPortfolio({ positions: {}, total_positions: 0 });
          nextErrors.push('portfolio');
        }

        const watchlistRes = results[1];
        if (watchlistRes.status === 'fulfilled') {
          setWatchlist(watchlistRes.value || { chat_id: null, symbols: [], watchlists: {} });
        } else {
          setWatchlist({ chat_id: null, symbols: [], watchlists: {} });
          nextErrors.push('watchlist');
        }

        const scanRes = results[2];
        if (scanRes.status === 'fulfilled') {
          setScan(scanRes.value || null);
        } else {
          setScan({ universe: 'bist30', analyzed_count: 0, failed_count: 0, oversold: [], overbought: [], strong_trend: [] });
          nextErrors.push('scan');
        }

        setSectionErrors(nextErrors);
        if (nextErrors.length === 3) {
          setError('Failed to load dashboard data');
        }
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  const watchlistCount = useMemo(() => {
    if (Array.isArray(watchlist.symbols) && watchlist.symbols.length > 0) {
      return watchlist.symbols.length;
    }
    const groups = watchlist.watchlists || {};
    return Object.values(groups).reduce((sum, list) => sum + (Array.isArray(list) ? list.length : 0), 0);
  }, [watchlist]);

  const scanCandidates = useMemo(() => collectScanCandidates(scan), [scan]);

  const topWinner = useMemo(() => {
    const rows = scanCandidates.filter((x) => typeof x.change_pct === 'number');
    if (!rows.length) return null;
    return rows.reduce((best, current) => (current.change_pct > best.change_pct ? current : best));
  }, [scanCandidates]);

  const topLoser = useMemo(() => {
    const rows = scanCandidates.filter((x) => typeof x.change_pct === 'number');
    if (!rows.length) return null;
    return rows.reduce((worst, current) => (current.change_pct < worst.change_pct ? current : worst));
  }, [scanCandidates]);

  const dailyPulse = useMemo(() => {
    const rows = scanCandidates.filter((x) => typeof x.change_pct === 'number');
    if (!rows.length) return null;
    const avg = rows.reduce((sum, x) => sum + x.change_pct, 0) / rows.length;
    return avg;
  }, [scanCandidates]);

  const marketScore = useMemo(() => {
    if (!scanCandidates.length) return 0;
    const pos = positiveCount(scanCandidates);
    const neg = negativeCount(scanCandidates);
    const balance = pos + neg === 0 ? 50 : 50 + ((pos - neg) / (pos + neg)) * 50;
    return clampScore(balance);
  }, [scanCandidates]);

  const momentumScore = useMemo(() => {
    if (dailyPulse === null) return 0;
    return clampScore(50 + dailyPulse * 8);
  }, [dailyPulse]);

  const stabilityScore = useMemo(() => {
    const total = scan?.analyzed_count || 0;
    if (!total) return 0;
    const failure = scan?.failed_count || 0;
    return clampScore(((total - failure) / total) * 100);
  }, [scan]);

  return (
    <section className="dash-pro">
      <h2>Dashboard</h2>
      <p className="muted">Quick portfolio and BIST30 snapshot</p>

      {loading && (
        <div className="dash-skeleton-grid">
          <div className="card skeleton-card"><span className="skeleton-line skeleton-title" /><span className="skeleton-line" /></div>
          <div className="card skeleton-card"><span className="skeleton-line skeleton-title" /><span className="skeleton-line" /></div>
          <div className="card skeleton-card"><span className="skeleton-line skeleton-title" /><span className="skeleton-line" /></div>
          <div className="card skeleton-card"><span className="skeleton-line skeleton-title" /><span className="skeleton-line" /></div>
        </div>
      )}
      {!loading && error && <div className="card"><p className="muted">{error}</p></div>}
      {!loading && !error && sectionErrors.length > 0 && (
        <div className="card"><p className="muted">Partial data loaded. Missing sections: {sectionErrors.join(', ')}</p></div>
      )}

      {!loading && !error && (
        <>
          <div className="dash-grid">
            <div className="card dash-card dash-anim">
              <p className="dash-label">Portfolio Positions</p>
              <p className="dash-value">{portfolio.total_positions ?? 0}</p>
              <div className="dash-card-glow" />
            </div>

            <div className="card dash-card dash-anim">
              <p className="dash-label">Watchlist Symbols</p>
              <p className="dash-value">{watchlistCount}</p>
              <div className="dash-card-glow" />
            </div>

            <div className="card dash-card dash-anim">
              <p className="dash-label">Daily Pulse</p>
              <p className="dash-value">{dailyPulse === null ? 'n/a' : formatPct(dailyPulse)}</p>
              <p className="muted">BIST30 scan sample</p>
              <div className="dash-card-glow" />
            </div>

            <div className="card dash-card dash-anim">
              <p className="dash-label">Active Alerts</p>
              <p className="dash-value">—</p>
              <p className="muted">Alerts API not connected yet</p>
              <div className="dash-card-glow" />
            </div>
          </div>

          <div className="card dash-progress-panel dash-fade">
            <h3>Market Quality Signals</h3>
            <div className="dash-progress-row">
              <span>Market Breadth</span>
              <span>{marketScore}/100</span>
            </div>
            <div className="dash-progress-track"><div className="dash-progress-fill" style={{ width: `${marketScore}%` }} /></div>

            <div className="dash-progress-row">
              <span>Momentum</span>
              <span>{momentumScore}/100</span>
            </div>
            <div className="dash-progress-track"><div className="dash-progress-fill" style={{ width: `${momentumScore}%` }} /></div>

            <div className="dash-progress-row">
              <span>Data Stability</span>
              <span>{stabilityScore}/100</span>
            </div>
            <div className="dash-progress-track"><div className="dash-progress-fill" style={{ width: `${stabilityScore}%` }} /></div>
          </div>

          <div className="dash-split">
            <div className="card dash-fade dash-summary-card">
              <h3>Top Winner / Loser</h3>
              <ul className="list">
                <li>
                  <span className="dash-k-label">Winner:</span>{' '}
                  <span className="dash-k-value">
                    {topWinner ? `${topWinner.symbol} (${formatPct(topWinner.change_pct)})` : 'n/a'}
                  </span>
                </li>
                <li>
                  <span className="dash-k-label">Loser:</span>{' '}
                  <span className="dash-k-value">
                    {topLoser ? `${topLoser.symbol} (${formatPct(topLoser.change_pct)})` : 'n/a'}
                  </span>
                </li>
              </ul>
            </div>

            <div className="card dash-fade dash-summary-card">
              <h3>Quick Scan Summary</h3>
              <ul className="list">
                <li><span className="dash-k-label">Analyzed:</span> <span className="dash-k-value">{scan?.analyzed_count ?? 0}</span></li>
                <li><span className="dash-k-label">Oversold:</span> <span className="dash-k-value">{scan?.oversold?.length ?? 0}</span></li>
                <li><span className="dash-k-label">Overbought:</span> <span className="dash-k-value">{scan?.overbought?.length ?? 0}</span></li>
                <li><span className="dash-k-label">Strong Trend:</span> <span className="dash-k-value">{scan?.strong_trend?.length ?? 0}</span></li>
              </ul>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
