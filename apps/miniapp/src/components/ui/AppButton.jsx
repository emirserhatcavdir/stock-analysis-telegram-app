export default function AppButton({
  type = 'button',
  onClick,
  disabled = false,
  children,
  variant = 'primary',
  className = '',
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      aria-disabled={disabled}
      className={`ds-btn ds-btn-${variant} ${className}`.trim()}
    >
      {children}
    </button>
  );
}
