import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import './ProductDetail.css';
import { fetchProduct } from '../services/product';
import { addToCart } from '../services/cart';
import { TOKEN_KEY } from '../services/api';

const ProductDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();

  const [product, setProduct] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const options = product?.options || [];
  const colors = [...new Set(options.map((o) => o.color))];
  const sizesForColor = (color) => options.filter((o) => o.color === color).map((o) => o.size);

  const [selectedOption, setSelectedOption] = useState(null); // {id,color,size}
  const [quantity, setQuantity] = useState(1);
  const [adding, setAdding] = useState(false);
  const [addedMsg, setAddedMsg] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');
    fetchProduct(id)
      .then((data) => { if (!cancelled) { setProduct(data); setSelectedOption(null); } })
      .catch(() => !cancelled && setError('상품을 불러오지 못했습니다.'))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [id]);

  const stockOf = (opt) => opt?.quantity ?? product.stock_quantity;

  const handleAddToCart = async () => {
    if (!localStorage.getItem(TOKEN_KEY)) {
      navigate('/login');
      return;
    }
    setAdding(true);
    setAddedMsg('');
    try {
      await addToCart({
        productId: product.id,
        optionId: selectedOption?.id ?? null,
        color: selectedOption?.color,
        size: selectedOption?.size,
        quantity,
      });
      navigate('/cart');
    } catch (err) {
      setAddedMsg(err.response?.data?.error || '장바구니에 담지 못했습니다.');
    } finally {
      setAdding(false);
    }
  };

  if (loading) return <div className="state-message">상품을 불러오는 중...</div>;
  if (error) {
    return (
      <div className="state-message error">
        {error} <Link to="/products">목록으로</Link>
      </div>
    );
  }

  const mainImage = product.images?.find((i) => i.isPrimary)?.url || product.images?.[0]?.url;
  const hasOptions = options.length > 0;
  const optionReady = !!(selectedOption && selectedOption.id);
  const stockText = !hasOptions
    ? `재고 ${product.stock_quantity}개`
    : !optionReady
      ? selectedOption?.color
        ? `${selectedOption.color} - 사이즈를 선택하세요`
        : '색상과 사이즈를 선택하세요'
      : `${selectedOption.color} / ${selectedOption.size} - 재고 ${stockOf(selectedOption)}개`;

  return (
    <div className="product-detail">
      <div className="product-images">
        {mainImage ? <img src={mainImage} alt={product.name} /> : <div className="no-image-large">이미지 없음</div>}
      </div>

      <div className="product-info">
        <span className="category-tag">{product.category_name}</span>
        <h1>{product.name}</h1>
        <p className="price">₩{Number(product.price).toLocaleString()}</p>
        <div className="product-description"><p>{product.description || '설명 없음'}</p></div>

        {hasOptions ? (
          <div className="product-options">
            <div className="option-group">
              <label>색상</label>
              <div className="color-selector">
                {colors.map((c) => {
                  const active = selectedOption?.color === c;
                  return (
                    <button
                      key={c}
                      type="button"
                      className={`color-option ${active ? 'selected' : ''}`}
                      onClick={() => setSelectedOption({ color: c, size: null })}
                    >
                      {c}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="option-group">
              <label>사이즈</label>
              <select
                value={selectedOption?.size || ''}
                disabled={!selectedOption?.color}
                onChange={(e) => {
                  const size = e.target.value;
                  if (!size) return;
                  const opt = options.find((o) => o.color === selectedOption.color && o.size === size);
                  // quantity까지 담아야 재고 표시/게이트가 옵션 실재고를 사용한다 (없으면 product.stock_quantity로 잘못 표시됨)
                  setSelectedOption(opt ? { id: opt.id, color: opt.color, size: opt.size, quantity: opt.quantity } : null);
                }}
              >
                <option value="" disabled>선택</option>
                {(selectedOption?.color ? sizesForColor(selectedOption.color) : []).map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>

            <div className="option-group">
              <label>수량</label>
              <div className="quantity-control">
                <button type="button" onClick={() => setQuantity(Math.max(1, quantity - 1))}>-</button>
                <span>{quantity}</span>
                <button type="button" onClick={() => setQuantity(quantity + 1)}>+</button>
              </div>
            </div>

            <p className={`stock-line ${selectedOption && stockOf(selectedOption) === 0 ? 'out' : ''}`}>
              {selectedOption && stockOf(selectedOption) === 0 ? '재고 없음' : stockText}
            </p>
          </div>
        ) : (
          <p className="stock-line">{stockText}</p>
        )}

        <div className="action-buttons">
          {/* 옵션 상품: 색상+사이즈까지(optionReady) 선택 전엔 담기 불가 — 색상만으로는 option_id 없이 기본 재고로 빠져나가는 것 방지 */}
          <button type="button" className="add-to-cart" onClick={handleAddToCart} disabled={adding || (hasOptions && !optionReady)}>
            {adding ? '담는 중...' : '장바구니에 담기'}
          </button>
          <Link to="/products" className="back-link">목록으로</Link>
        </div>

        {addedMsg && <div className="error-message">{addedMsg}</div>}
      </div>
    </div>
  );
};

export default ProductDetail;
