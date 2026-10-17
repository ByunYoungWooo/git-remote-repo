import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import './Checkout.css';
import { fetchCart } from '../services/cart';
import { createOrder } from '../services/order';

const Checkout = () => {
  const [cart, setCart] = useState(null);
  const [shippingAddress, setShippingAddress] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [placed, setPlaced] = useState(null); // {orderId,totalAmount}
  const navigate = useNavigate();

  useEffect(() => {
    fetchCart()
      .then(setCart)
      .catch((err) => setError(err.response?.data?.error || '장바구니를 불러오지 못했습니다.'));
  }, []);

  if (placed) {
    return (
      <div className="checkout-success">
        <h1>주문이 접수되었습니다</h1>
        <p>주문번호: #{placed.orderId}</p>
        <p>합계: ₩{Number(placed.totalAmount).toLocaleString()}</p>
        <p className="note">결제는 아직 개발 중입니다. 주문은 'pending' 상태로 보관됩니다.</p>
        <div className="success-actions">
          <Link to="/products" className="primary-button">쇼핑 계속하기</Link>
          <button type="button" onClick={() => navigate('/orders')}>내 주문 보기</button>
        </div>
      </div>
    );
  }

  const submit = async (e) => {
    e.preventDefault();
    if (!cart || cart.items.length === 0) return;
    setSubmitting(true);
    setError('');
    try {
      const result = await createOrder({ shippingAddress: shippingAddress.trim() });
      setPlaced(result);
    } catch (err) {
      setError(err.response?.data?.error || '주문에 실패했습니다.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="checkout">
      <h1>주문 확인</h1>
      {cart && cart.items.length === 0 ? (
        <div className="state-message"><Link to="/products">장바구니가 비어 있습니다.</Link></div>
      ) : (
        <>
          {error && <div className="error-message">{error}</div>}

          <form onSubmit={submit} className="checkout-form">
            <div className="order-items">
              {cart?.items.map((item) => (
                <div key={item.cartId} className="order-item-row">
                  <span>{item.name}{item.color ? ` (${item.color}/${item.size})` : ''}</span>
                  <span>x{item.quantity}</span>
                  <span>₩{item.lineTotal.toLocaleString()}</span>
                </div>
              ))}
            </div>

            <label className="address-label">배송 주소</label>
            <textarea
              value={shippingAddress}
              onChange={(e) => setShippingAddress(e.target.value)}
              placeholder="받는 사람과 주소를 입력하세요 (선택)"
              rows={3}
            />

            <div className="total-line">총액: <strong>₩{Number(cart?.totalAmount || 0).toLocaleString()}</strong></div>

            <button type="submit" className="primary-button" disabled={submitting}>
              {submitting ? '주문 접수 중...' : '주문하기 (결제 없이)'}
            </button>
          </form>
        </>
      )}
    </div>
  );
};

export default Checkout;
