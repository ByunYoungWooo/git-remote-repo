import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import './Orders.css';
import { fetchOrders } from '../services/order';
import { TOKEN_KEY } from '../services/api';

const STATUS_LABEL = { pending: '결제 대기', paid: '결제 완료', cancelled: '취소' };

const Orders = () => {
  const [orders, setOrders] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const loggedIn = !!localStorage.getItem(TOKEN_KEY);

  useEffect(() => {
    if (!loggedIn) return;
    fetchOrders()
      .then((res) => setOrders(res.orders || []))
      .catch((err) => setError(err.response?.data?.error || '주문을 불러오지 못했습니다.'));
    setLoading(false);
  }, [loggedIn]);

  if (!loggedIn) {
    return (
      <div className="orders">
        <h1>내 주문</h1>
        <p className="note">로그인 후 주문 내역을 확인하세요.</p>
        <Link to="/login" className="primary-button">로그인</Link>
      </div>
    );
  }

  if (loading) return <div className="state-message">주문을 불러오는 중...</div>;

  if (!orders || orders.length === 0) {
    return (
      <div className="orders-empty">
        <h1>내 주문</h1>
        <p className="note">아직 주문 내역이 없습니다.</p>
        <Link to="/products" className="primary-button">쇼핑 시작하기</Link>
      </div>
    );
  }

  return (
    <div className="orders">
      <h1>내 주문</h1>
      {error && <div className="error-message">{error}</div>}

      <ul className="order-list">
        {orders.map((o) => (
          <li key={o.id} className="order-row" onClick={() => navigate(`/orders/${o.id}`)}>
            <span className="order-id"># {o.id}</span>
            <span className={`status status-${o.status}`}>{STATUS_LABEL[o.status] || o.status}</span>
            <span className="order-date">
              {new Date(o.createdAt).toLocaleDateString('ko-KR')}{' '}
              {new Date(o.createdAt).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}
            </span>
            <span className="order-items-count">{o.itemCount}개 상품</span>
            <strong className="order-total">₩{Number(o.totalAmount).toLocaleString()}</strong>
          </li>
        ))}
      </ul>

      <p className="hint">주문을 클릭하면 상세 내역을 볼 수 있습니다.</p>
    </div>
  );
};

export default Orders;
