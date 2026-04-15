import { useId } from 'react';

function toNumber(value) {
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function pointsToPath(values, width, height, padding) {
  if (!Array.isArray(values) || values.length < 2) return '';

  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = (width - padding * 2) / (values.length - 1);

  return values
    .map((value, index) => {
      const x = padding + index * step;
      const y = padding + ((max - value) / span) * (height - padding * 2);
      return `${index === 0 ? 'M' : 'L'}${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(' ');
}

export default function MiniSparkline({ points = [], width = 120, height = 36, className = '' }) {
  const id = useId().replace(/:/g, '');
  const values = points
    .map((row) => toNumber(row?.close))
    .filter((value) => typeof value === 'number');

  if (values.length < 2) {
    return <div className={`ds-sparkline ds-sparkline-empty ${className}`.trim()} aria-hidden="true" />;
  }

  const first = values[0];
  const last = values[values.length - 1];
  const up = last >= first;
  const stroke = up ? '#74d9b8' : '#ef90a8';
  const gradientId = `spark-${id}-${up ? 'up' : 'down'}`;
  const path = pointsToPath(values, width, height, 2);

  return (
    <svg className={`ds-sparkline ${className}`.trim()} width={width} height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.28" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={`${path} L ${width - 2} ${height - 2} L 2 ${height - 2} Z`} fill={`url(#${gradientId})`} />
      <path d={path} fill="none" stroke={stroke} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
