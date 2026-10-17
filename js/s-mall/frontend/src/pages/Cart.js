import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import './Cart.css';
import { fetchCart, updateCartQuantity, removeFromCart } from '../services/cart';
import { TOKEN_KEY } from '../services/api';

const Cart = () => {
  const [cart, setCart] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actingId, setActingId] = useState(null);
  const navigate = useNavigate();

  const loggedIn = !!localStorage.getItem(TOKEN_KEY);

  const load = useCallback(async () => {
    if (!loggedIn) return;
    setLoading(true);
    setError('');
    try {
      setCart(await fetchCart());
    } catch (err) {
      setError(err.response?.data?.error || '장바구니를 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  }, [loggedIn]);

  useEffect(() => { load(); }, [load]);

  const changeQty = async (item, delta) => {
    const next = Math.max(1, item.quantity + delta);
    if (next === item.quantity) return;
    setActingId(item.cartId);
    try {
      await updateCartQuantity(item.cartId, next);
      setCart(await fetchCart());
    } catch (err) {
      setError(err.response?.data?.error || '수량 변경에 실패했습니다.');
    } finally {
      setActingId(null);
    }
  };

  const remove = async (item) => {
    setActingId(item.cartId);
    try {
      await removeFromCart(item.cartId);
      setCart(await fetchCart());
    } catch (err) {
      setError(err.response?.data?.error || '삭제에 실패했습니다.');
    } finally {
      setActingId(null);
    }
  };

  if (!loggedIn) {
    return (
      <div className="cart-empty">
        <h2>장바구니</h2>
        <p>로그인 후 장바구니를 확인하세요.</p>
        <Link to="/login" className="primary-button">로그인</Link>
      </div>
    );
  }

  if (loading) return <div className="state-message">장바구니를 불러오는 중...</div>;

  if (!cart || cart.items.length === 0) {
    return (
      <div className="cart-empty">
        <h2>장바구니가 비어 있습니다</h2>
        <Link to="/products" className="primary-button">쇼핑 계속하기</Link>
      </div>
    );
  }

  return (
    <div className="cart">
      <h1>장바구니</h1>
      {error && <div className="error-message">{error}</div>}

      <div className="cart-items">
        {cart.items.map((item) => (
          <div key={item.cartId} className="cart-item">
            <div className="item-details">
              <h3>{item.name}</h3>
              {item.color && <p>{item.color} / {item.size}</p>}
            </div>
            <div className="item-quantity">
              <button type="button" disabled={actingId === item.cartId} onClick={() => changeQty(item, -1)}>-</button>
              <span>{item.quantity}</span>
              <button type="button" disabled={actingId === item.cartId} onClick={() => changeQty(item, +1)}>+</button>
            </div>
            <div className="item-price">₩{item.lineTotal.toLocaleString()}</div>
            <button type="button" className="remove-button" disabled={actingId === item.cartId} onClick={() => remove(item)}>
              삭제
            </button>
          </div>
        ))}
      </div>

      <div className="cart-summary">
        <h2>주문 요약</h2>
        <div className="summary-row"><span>상품 합계:</span><span>₩{cart.totalAmount.toLocaleString()}</span></div>
        <button type="button" className="checkout-button" onClick={() => navigate('/checkout')}>
          주문하기
        </button>
      </div>
    </div>
  );
};

export default Cart;
