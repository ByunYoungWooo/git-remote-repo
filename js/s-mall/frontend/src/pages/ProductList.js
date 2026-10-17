import React, { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import './ProductList.css';
import { fetchProducts } from '../services/product';

const SORT_LABELS = {
  created_at_desc: '최신순',
  price_asc: '가격 낮은 순',
  price_desc: '높은 순',
  name: '이름순',
};

const ProductList = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [pagination, setPagination] = useState({ page: 1, limit: 12, total: 0 });

  const categoryId = searchParams.get('categoryId') || '';
  const sort = searchParams.get('sort') || 'created_at_desc';
  const search = searchParams.get('search') || '';
  const searchInput = searchParams.get('search') || '';

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');

    fetchProducts({ categoryId, sort, search: search || undefined, limit: 12 })
      .then((data) => {
        if (cancelled) return;
        setProducts(data.products || []);
        setPagination(data.pagination || { page: 1, limit: 12, total: data.products?.length || 0 });
      })
      .catch((err) => {
        if (!cancelled) setError('상품을 불러오지 못했습니다.');
      })
      .finally(() => !cancelled && setLoading(false));

    return () => { cancelled = true; };
  }, [categoryId, sort, search]);

  const setParam = (key, value) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value); else next.delete(key);
    setSearchParams(next);
  };

  return (
    <div className="product-list">
      <h1>모든 상품</h1>

      <div className="list-controls">
        <input
          type="search"
          placeholder="상품 검색"
          defaultValue={searchInput}
          onKeyDown={(e) => { if (e.key === 'Enter') setParam('search', e.target.value.trim()); }}
        />
        <select value={sort} onChange={(e) => setParam('sort', e.target.value)}>
          {Object.entries(SORT_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </div>

      {loading && <div className="state-message">상품을 불러오는 중...</div>}
      {!loading && error && <div className="state-message error">{error}</div>}
      {!loading && !error && products.length === 0 && (
        <div className="state-message">조건에 맞는 상품이 없습니다.</div>
      )}

      <div className="product-grid">
        {products.map((p) => {
          const img = p.images?.find((i) => i.isPrimary)?.url || p.images?.[0]?.url;
          return (
            <Link to={`/product/${p.id}`} key={p.id} className="product-card">
              {img ? (
                <img src={img} alt={p.name} loading="lazy" />
              ) : (
                <div className="no-image">이미지 없음</div>
              )}
              <h3>{p.name}</h3>
              <p>₩{Number(p.price).toLocaleString()}</p>
            </Link>
          );
        })}
      </div>

      {pagination.total > 0 && (
        <div className="result-count">총 {pagination.total}개 상품</div>
      )}
    </div>
  );
};

export default ProductList;
