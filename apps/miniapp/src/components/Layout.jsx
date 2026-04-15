import { useEffect, useMemo } from 'react';
import NavBar from './NavBar';
import BetaBanner from './ui/BetaBanner';
import { getTelegramContext, initTelegramWebApp } from '../lib/telegram';

export default function Layout({ children }) {
  useEffect(() => {
    initTelegramWebApp();
  }, []);

  const tg = useMemo(() => getTelegramContext(), []);
  const shellClass = tg.isTelegram ? 'app-shell is-telegram' : 'app-shell';

  return (
    <div className={shellClass} data-theme={tg.colorScheme}>
      <header className="app-header">
        <h1>BIST Mini App</h1>
        <p>
          {tg.isTelegram
            ? `Telegram mode${tg.platform ? ` • ${tg.platform}` : ''}`
            : 'Browser preview mode'}
        </p>
      </header>
      <BetaBanner />
      <NavBar />
      <main className="app-main">{children}</main>
    </div>
  );
}
