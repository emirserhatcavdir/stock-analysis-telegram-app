function applyThemeParams(tg) {
  if (typeof document === 'undefined' || !tg?.themeParams) return;

  const root = document.documentElement;
  const params = tg.themeParams;

  if (params.bg_color) root.style.setProperty('--tg-bg', params.bg_color);
  if (params.secondary_bg_color) root.style.setProperty('--tg-surface', params.secondary_bg_color);
  if (params.text_color) root.style.setProperty('--tg-text', params.text_color);
  if (params.hint_color) root.style.setProperty('--tg-muted', params.hint_color);
  if (params.button_color) root.style.setProperty('--tg-accent', params.button_color);
  if (params.button_text_color) root.style.setProperty('--tg-accent-text', params.button_text_color);
}

export function initTelegramWebApp() {
  if (typeof window === 'undefined') return null;

  const tg = window.Telegram?.WebApp;
  if (!tg) return null;

  try {
    tg.ready();
    tg.expand();
    tg.enableClosingConfirmation?.();
    tg.disableVerticalSwipes?.();
    applyThemeParams(tg);
  } catch {
    return null;
  }
  return tg;
}

export function getTelegramContext() {
  if (typeof window === 'undefined') {
    return {
      isTelegram: false,
      user: null,
      colorScheme: 'light',
    };
  }

  const tg = window.Telegram?.WebApp;
  const viewportHeight = typeof tg?.viewportHeight === 'number' ? tg.viewportHeight : null;
  return {
    isTelegram: Boolean(tg),
    user: tg?.initDataUnsafe?.user ?? null,
    colorScheme: tg?.colorScheme ?? 'light',
    viewportHeight,
    platform: tg?.platform ?? null,
  };
}

export function getEffectiveUserId() {
  const ctx = getTelegramContext();
  const telegramId = ctx?.user?.id;
  if (telegramId !== undefined && telegramId !== null && String(telegramId).trim() !== '') {
    return String(telegramId).trim();
  }

  const fallback = String(import.meta.env.VITE_DEV_USER_ID || '').trim();
  return fallback || '';
}
