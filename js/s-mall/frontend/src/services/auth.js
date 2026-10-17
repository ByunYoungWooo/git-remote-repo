// 인증 관련 API
import api from './api';

export async function register({ username, email, password }) {
  const res = await api.post('/auth/register', { username, email, password });
  return res.data;
}

export async function login({ email, password }) {
  const res = await api.post('/auth/login', { email, password });
  return res.data;
}
