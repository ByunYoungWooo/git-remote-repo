import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import './Orders.css';
import api, { TOKEN_KEY } from '../services/api';

const STATUS_LABEL = { pending: '결제 대기', paid: '결제 완료', cancelled: '취소' };

const OrderDetail = () => {
  const { id } = useParams();
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!localStorage.getItem(TOKEN_KEY)) return;
    api.get(`/orders/${id}`)
      .then((res) => setOrder(res.data))
      .catch((err) => setError(err.response?.data?.error || '주문을 찾을 수 없습니다.'));
    setLoading(false);
  }, [id]);

  if (loading) return <div className="state-message">주문 상세를 불러오는 중...</div>;

  if (!order) {
    return (
      <div className="orders-empty">
        {error && <p className="note">{error}</p>}
        <Link to="/orders" className="primary-button">내 주문 목록으로</Link>
      </div>
    );
  }

  const items = order.items || [];
  return (
    <div className="order-detail">
      <h1>주문 # {order.id}</h1>
      <div className="detail-meta">
        <span className={`status status-${order.status}`}>{STATUS_LABEL[order.status] || order.status}</span>
        <span>{new Date(order.createdAt).toLocaleString('ko-KR')}</span>
        <strong>₩{Number(order.totalAmount).toLocaleString()}</strong>
      </div>

      {order.shippingAddress && (
        <div className="detail-address">배송 주소: {order.shippingAddress}</div>
      )}

      <table className="detail-table">
        <thead>
          <tr><th>상품명</th><th>수량</th><th>단가</th><th>소계</th></tr>
        </thead>
        <tbody>
          {items.map((it, i) => (
            <tr key={i}>
              <td>{it.name}</td>
              <td>x{it.quantity}</td>
              <td>₩{Number(it.price).toLocaleString()}</td>
              <td>₩{Number(it.lineTotal ?? it.price * it.quantity).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="detail-actions">
        <Link to="/orders" className="primary-button">내 주문 목록</Link>
      </div>
    </div>
  );
};

export default OrderDetail;
