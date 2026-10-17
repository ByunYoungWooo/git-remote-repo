// 상품 관련 API
import api from './api';

export async function fetchProducts(params = {}) {
  const res = await api.get('/products', { params });
  return res.data;
}

export async function fetchProduct(id) {
  const res = await api.get(`/products/${id}`);
  return res.data;
}
