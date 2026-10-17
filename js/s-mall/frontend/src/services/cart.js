// 장바구니 관련 API
import api from './api';

export async function fetchCart() {
  const res = await api.get('/cart');
  return res.data;
}

export async function addToCart({ productId, optionId, color, size, quantity }) {
  const payload = { productId, quantity: quantity || 1 };
  if (optionId) payload.optionId = optionId;
  if (color) payload.color = color;
  if (size) payload.size = size;
  const res = await api.post('/cart/items', payload);
  return res.data;
}

export async function updateCartQuantity(cartId, quantity) {
  const res = await api.patch(`/cart/items/${cartId}`, { quantity });
  return res.data;
}

export async function removeFromCart(cartId) {
  const res = await api.delete(`/cart/items/${cartId}`);
  return res.data;
}
