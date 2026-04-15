const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').trim();

function buildApiUrl(path) {
  if (!API_BASE) return path;
  const base = API_BASE.endsWith('/') ? API_BASE.slice(0, -1) : API_BASE;
  let suffix = path.startsWith('/') ? path : `/${path}`;
  // If API_BASE already includes /api, avoid generating /api/api/* paths.
  if (base.endsWith('/api') && suffix.startsWith('/api/')) {
    suffix = suffix.slice(4);
  }
  return `${base}${suffix}`;
}

async function getJson(path) {
  const response = await fetch(buildApiUrl(path));
  const contentType = response.headers.get('content-type') || '';
  const isJson = contentType.includes('application/json');

  if (!response.ok) {
    if (isJson) {
      try {
        const payload = await response.json();
        const detail = payload?.detail ? ` - ${payload.detail}` : '';
        throw new Error(`Request failed: ${response.status}${detail}`);
      } catch {
        throw new Error(`Request failed: ${response.status}`);
      }
    }
    throw new Error(`Request failed: ${response.status}`);
  }

  if (!isJson) {
    const preview = (await response.text()).slice(0, 80);
    throw new Error(`Expected JSON response but received non-JSON content. ${preview}`);
  }

  return response.json();
}

function toQueryString(params = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    query.append(key, String(value));
  });
  const serialized = query.toString();
  return serialized ? `?${serialized}` : '';
}

function toUserIdNumber(userId) {
  const value = Number(userId);
  return Number.isFinite(value) && value > 0 ? Math.trunc(value) : undefined;
}

function userQuery(userId) {
  const numericUserId = toUserIdNumber(userId);
  if (!numericUserId) return '';
  return toQueryString({ user_id: numericUserId });
}

async function postJson(path, payload) {
  const response = await fetch(buildApiUrl(path), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  const contentType = response.headers.get('content-type') || '';
  const isJson = contentType.includes('application/json');

  if (!response.ok) {
    if (isJson) {
      try {
        const body = await response.json();
        const detail = body?.detail ? ` - ${body.detail}` : '';
        throw new Error(`Request failed: ${response.status}${detail}`);
      } catch {
        throw new Error(`Request failed: ${response.status}`);
      }
    }
    throw new Error(`Request failed: ${response.status}`);
  }

  if (!isJson) {
    const preview = (await response.text()).slice(0, 80);
    throw new Error(`Expected JSON response but received non-JSON content. ${preview}`);
  }

  return response.json();
}

export const api = {
  getPortfolio: (userId) => getJson(`/api/portfolio${userQuery(userId)}`),
  getWatchlist: (userId) => getJson(`/api/watchlist${userQuery(userId)}`),
  getAnalysis: (symbol, params = {}) =>
    getJson(`/api/analysis/${encodeURIComponent(symbol)}${toQueryString(params)}`),
  getScore: (symbol) => getJson(`/api/score/${encodeURIComponent(symbol)}`),
  getSymbol: (symbol) => getJson(`/symbol/${encodeURIComponent(symbol)}`),
  getSymbolChartSeries: (symbol, params = {}) =>
    getJson(`/symbol/${encodeURIComponent(symbol)}/chart-series${toQueryString(params)}`),
  getPortfolioInsights: (userId) => {
    const id = toUserIdNumber(userId);
    const path = id != null ? `/api/portfolio/insights?user_id=${id}` : '/api/portfolio/insights';
    return getJson(path);
  },
  getTradeHistory: (userId, limit = 20) => {
    const id = toUserIdNumber(userId);
    const safeLimit = Number.isFinite(Number(limit)) ? Number(limit) : 20;
    const path = id != null
      ? `/api/portfolio/trades?user_id=${id}&limit=${safeLimit}`
      : `/api/portfolio/trades?limit=${safeLimit}`;
    return getJson(path);
  },
  getBist30Scan: () => getJson('/api/scan/bist30'),
  getScan: (params = {}) => getJson(`/scan${toQueryString(params)}`),
  getRank: (params = {}) => getJson(`/rank${toQueryString(params)}`),
  buyPortfolio: ({ user_id, symbol, quantity, price }) =>
    postJson('/api/portfolio/buy', { user_id: toUserIdNumber(user_id), symbol, quantity, price }),
  sellPortfolio: ({ user_id, symbol, quantity, price }) =>
    postJson('/api/portfolio/sell', { user_id: toUserIdNumber(user_id), symbol, quantity, price }),
  addWatchlistItem: ({ user_id, symbol }) =>
    postJson('/api/watchlist/add', { user_id: toUserIdNumber(user_id), symbol }),
  removeWatchlistItem: ({ user_id, symbol }) =>
    postJson('/api/watchlist/remove', { user_id: toUserIdNumber(user_id), symbol }),
  getAlerts: (userId) => getJson(`/api/alerts/${encodeURIComponent(userId)}`),
  addAlert: (userId, payload) => postJson(`/api/alerts/${encodeURIComponent(userId)}/add`, payload),
  removeAlert: (userId, payload) => postJson(`/api/alerts/${encodeURIComponent(userId)}/remove`, payload),
};