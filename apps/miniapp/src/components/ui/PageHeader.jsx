export default function PageHeader({ title, subtitle, meta, actions = null }) {
  return (
    <header className="ds-page-header">
      <div className="ds-page-header-main">
        <p className="ds-eyebrow">Mini App</p>
        <h3>{title}</h3>
        {subtitle ? <p className="ds-subtitle">{subtitle}</p> : null}
      </div>
      <div className="ds-page-header-right">
        {meta ? <p className="ds-meta">{meta}</p> : null}
        {actions ? <div className="ds-actions">{actions}</div> : null}
      </div>
    </header>
  );
}
