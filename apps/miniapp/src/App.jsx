import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import DashboardPage from './pages/DashboardPage';
import PortfolioPage from './pages/PortfolioPage';
import WatchlistPage from './pages/WatchlistPage';
import ScanPage from './pages/ScanPage';
import SymbolDetailPage from './pages/SymbolDetailPage';
import AlertsPage from './pages/AlertsPage';

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/watchlist" element={<WatchlistPage />} />
        <Route path="/scan" element={<ScanPage />} />
        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="/symbol" element={<SymbolDetailPage />} />
        <Route path="/symbol/:symbol" element={<SymbolDetailPage />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Layout>
  );
}
