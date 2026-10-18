// API 클라이언트 - axios 인스턴스와 토큰 관리
import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:3001';

// NOTE: 두 키는 반드시 서로 달라야 한다 (동일 문자열이면 저장 충돌 → 401)
export const TOKEN_KEY = 's-mall-token';
export const USER_KEY = 's-mall-user';

const api = axios.create({ baseURL: API_BASE });

// 요청 인터셉터: 토큰 자동 첨부
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// 응답 인터셉터: 실패 시 로그 기록
api.interceptors.response.use(
  (r) => r,
  (err) => {
    try {
      const u = (err.config && err.config.url) || '?';
      const s = err.response ? err.response.status : '(network error)';
      console.warn('[axios-fail]', u, 'status=', s);
    } catch (e) {}
    return Promise.reject(err);
  }
);

export function saveSession(token, user) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function getStoredUser() {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}

export default api;
