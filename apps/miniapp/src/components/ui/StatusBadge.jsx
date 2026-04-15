export default function StatusBadge({ tone = 'neutral', children, className = '' }) {
  return <span className={`badge badge-${tone} ui-badge ${className}`.trim()}>{children}</span>;
}
