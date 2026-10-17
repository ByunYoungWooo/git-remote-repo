// 주문 관련 API
import api from './api';

export async function createOrder({ shippingAddress }) {
  const res = await api.post('/orders', { shippingAddress });
  return res.data;
}

export async function fetchOrders() {
  const res = await api.get('/orders');
  return res.data;
}
