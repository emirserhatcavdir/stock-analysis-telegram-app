import { useEffect, useMemo, useRef, useState } from 'react';
import { createChart, CrosshairMode } from 'lightweight-charts';

function toUnix(dateText) {
  const ms = Date.parse(`${dateText}T00:00:00Z`);
  if (!Number.isFinite(ms)) return null;
  return Math.floor(ms / 1000);
}

function fixed(value, digits = 2) {
  if (typeof value !== 'number' || Number.isNaN(value)) return 'n/a';
  return value.toFixed(digits);
}

function compactVolume(value) {
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

export default function TradingPriceChart({
  data,
  mode = 'candles',
  showMA20 = false,
  showMA50 = false,
  showMA200 = false,
  height = 312,
  onInspectChange,
}) {
  const wrapRef = useRef(null);
  const chartRef = useRef(null);
  const [inspect, setInspect] = useState(null);

  const prepared = useMemo(() => {
    const rows = [];
    for (const row of data || []) {
      const time = toUnix(row?.date);
      if (!time) continue;
      const close = typeof row?.close === 'number' ? row.close : null;
      if (close == null) continue;
      rows.push({
        date: row?.date,
        time,
        open: typeof row?.open === 'number' ? row.open : close,
        high: typeof row?.high === 'number' ? row.high : close,
        low: typeof row?.low === 'number' ? row.low : close,
        close,
        volume: typeof row?.volume === 'number' ? row.volume : null,
        ma20: typeof row?.ma20 === 'number' ? row.ma20 : null,
        ma50: typeof row?.ma50 === 'number' ? row.ma50 : null,
        ma200: typeof row?.ma200 === 'number' ? row.ma200 : null,
      });
    }
    return rows;
  }, [data]);

  useEffect(() => {
    if (!wrapRef.current || prepared.length === 0) return;

    const chart = createChart(wrapRef.current, {
      width: wrapRef.current.clientWidth,
      height,
      layout: {
        background: { color: '#0b1421' },
        textColor: '#9eb4cf',
        fontFamily: 'Manrope, Segoe UI, sans-serif',
      },
      grid: {
        vertLines: { color: 'rgba(79, 109, 148, 0.13)' },
        horzLines: { color: 'rgba(79, 109, 148, 0.15)' },
      },
      rightPriceScale: {
        borderColor: '#2a3d59',
        scaleMargins: {
          top: 0.06,
          bottom: 0.1,
        },
      },
      timeScale: {
        borderColor: '#2a3d59',
        timeVisible: true,
        rightOffset: 2,
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: 'rgba(132, 175, 236, 0.46)',
          width: 1,
          style: 2,
          labelBackgroundColor: '#203855',
        },
        horzLine: {
          color: 'rgba(132, 175, 236, 0.36)',
          width: 1,
          style: 2,
          labelBackgroundColor: '#203855',
        },
      },
      localization: {
        priceFormatter: (price) => fixed(price, 2),
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: false,
      },
      handleScale: {
        axisPressedMouseMove: true,
        mouseWheel: true,
        pinch: true,
      },
    });

    chartRef.current = chart;

    let mainSeries;
    if (mode === 'line') {
      mainSeries = chart.addLineSeries({
        color: '#89c4ff',
        lineWidth: 2.3,
        priceLineVisible: false,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 3,
      });
      mainSeries.setData(prepared.map((row) => ({ time: row.time, value: row.close })));
    } else {
      mainSeries = chart.addCandlestickSeries({
        upColor: '#62c7a6',
        downColor: '#df7a93',
        borderVisible: false,
        wickUpColor: '#8dd9c1',
        wickDownColor: '#ec9aaf',
        priceLineVisible: false,
      });
      mainSeries.setData(
        prepared.map((row) => ({
          time: row.time,
          open: row.open,
          high: row.high,
          low: row.low,
          close: row.close,
        }))
      );
    }

    const ma20Series = showMA20
      ? chart.addLineSeries({
          color: '#f3c183',
          lineWidth: 1.35,
          priceLineVisible: false,
          crosshairMarkerVisible: false,
        })
      : null;
    const ma50Series = showMA50
      ? chart.addLineSeries({
          color: '#79d9bd',
          lineWidth: 1.3,
          priceLineVisible: false,
          crosshairMarkerVisible: false,
        })
      : null;
    const ma200Series = showMA200
      ? chart.addLineSeries({
          color: '#ec97a8',
          lineWidth: 1.2,
          lineStyle: 2,
          priceLineVisible: false,
          crosshairMarkerVisible: false,
        })
      : null;

    if (ma20Series) {
      ma20Series.setData(prepared.filter((row) => row.ma20 != null).map((row) => ({ time: row.time, value: row.ma20 })));
    }
    if (ma50Series) {
      ma50Series.setData(prepared.filter((row) => row.ma50 != null).map((row) => ({ time: row.time, value: row.ma50 })));
    }
    if (ma200Series) {
      ma200Series.setData(prepared.filter((row) => row.ma200 != null).map((row) => ({ time: row.time, value: row.ma200 })));
    }

    chart.timeScale().fitContent();

    const onMove = (param) => {
      if (!param || !param.time) {
        setInspect(null);
        if (typeof onInspectChange === 'function') onInspectChange(null);
        return;
      }
      const row = prepared.find((item) => item.time === param.time);
      if (!row) {
        setInspect(null);
        if (typeof onInspectChange === 'function') onInspectChange(null);
        return;
      }
      setInspect(row);
      if (typeof onInspectChange === 'function') onInspectChange(row);
    };

    chart.subscribeCrosshairMove(onMove);

    const resize = () => {
      if (!wrapRef.current || !chartRef.current) return;
      chartRef.current.applyOptions({ width: wrapRef.current.clientWidth });
    };
    window.addEventListener('resize', resize);

    return () => {
      window.removeEventListener('resize', resize);
      chart.unsubscribeCrosshairMove(onMove);
      if (typeof onInspectChange === 'function') onInspectChange(null);
      chart.remove();
      chartRef.current = null;
    };
  }, [prepared, mode, showMA20, showMA50, showMA200, height, onInspectChange]);

  return (
    <div className="ds-terminal-wrap">
      <div className="ds-terminal-head">
        <span className="ds-terminal-mode">{mode === 'candles' ? 'Candles' : 'Line'}</span>
        <div className="ds-terminal-kv">
          <span className="ds-terminal-pill"><small>O</small><strong>{fixed(inspect?.open)}</strong></span>
          <span className="ds-terminal-pill"><small>H</small><strong>{fixed(inspect?.high)}</strong></span>
          <span className="ds-terminal-pill"><small>L</small><strong>{fixed(inspect?.low)}</strong></span>
          <span className="ds-terminal-pill"><small>C</small><strong>{fixed(inspect?.close)}</strong></span>
          <span className="ds-terminal-pill ds-terminal-pill-volume"><small>V</small><strong>{compactVolume(inspect?.volume)}</strong></span>
        </div>
      </div>
      <div ref={wrapRef} className="ds-terminal-chart" />
    </div>
  );
}
