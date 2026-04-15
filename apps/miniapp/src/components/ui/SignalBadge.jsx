const TONE_MAP = {
  positive: 'positive',
  negative: 'negative',
  neutral: 'neutral',
};

export default function SignalBadge({ tone = 'neutral', children }) {
  const normalized = TONE_MAP[tone] || 'neutral';
  return <span className={`ds-badge ds-badge-${normalized}`}>{children}</span>;
}
