import Card from './Card';

export default function SkeletonCard({ className = '' }) {
  return (
    <Card className={`skeleton-card ${className}`.trim()}>
      <span className="skeleton-line skeleton-title" />
      <span className="skeleton-line" />
    </Card>
  );
}
