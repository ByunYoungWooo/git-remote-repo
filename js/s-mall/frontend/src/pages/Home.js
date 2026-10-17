import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import './Home.css';
import { fetchProducts } from '../services/product';

const Home = () => {
  const [products, setProducts] = useState([]);

  useEffect(() => {
    fetchProducts({ limit: 4 })
      .then((data) => setProducts(data.products || []))
      .catch(() => {});
  }, []);

  return (
    <div className="home">
      <section className="hero">
        <h1>s-mall</h1>
        <p>당신만의 스타일을 찾아보세요</p>
        <Link to="/products" className="primary-button hero-cta">상품 보러가기</Link>
      </section>

      {products.length > 0 && (
        <section className="featured-products">
          <h2>추천 상품</h2>
          <div className="product-grid">
            {products.map((p) => {
              const img = p.images?.find((i) => i.isPrimary)?.url || p.images?.[0]?.url;
              return (
                <Link to={`/product/${p.id}`} key={p.id} className="product-card">
                  {img ? <img src={img} alt={p.name} loading="lazy" /> : <div className="no-image">이미지 없음</div>}
                  <h3>{p.name}</h3>
                  <p>₩{Number(p.price).toLocaleString()}</p>
                </Link>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
};

export default Home;
