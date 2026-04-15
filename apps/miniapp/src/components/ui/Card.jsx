export default function Card({ children, className = '' }) {
  return <div className={`card ui-card ${className}`.trim()}>{children}</div>;
}
