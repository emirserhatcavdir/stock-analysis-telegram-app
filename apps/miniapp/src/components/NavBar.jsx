import { NavLink } from 'react-router-dom';

const links = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/portfolio', label: 'Portfolio' },
  { to: '/watchlist', label: 'Watchlist' },
  { to: '/scan', label: 'Scan' },
  { to: '/alerts', label: 'Alerts' },
];

export default function NavBar() {
  return (
    <nav className="nav nav-segmented" aria-label="Primary">
      {links.map((link) => (
        <NavLink
          key={link.to}
          to={link.to}
          className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
        >
          {link.label}
        </NavLink>
      ))}
    </nav>
  );
}
