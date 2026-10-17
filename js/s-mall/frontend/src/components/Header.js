import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import './Header.css';
import { getStoredUser, clearSession, TOKEN_KEY } from '../services/api';

const Header = () => {
  const [user, setUser] = useState(getStoredUser());
  const navigate = useNavigate();

  useEffect(() => {
    if (localStorage.getItem(TOKEN_KEY)) {
      setUser((u) => u || getStoredUser());
    }
  }, []);

  const handleLogout = () => {
    clearSession();
    setUser(null);
    navigate('/');
  };

  return (
    <header className="header">
      <div className="container">
        <Link to="/" className="logo">s-mall</Link>
        <nav className="navigation">
          <Link to="/">홈</Link>
          <Link to="/products">상품</Link>
          <Link to="/cart">장바구니</Link>
          {user ? (
            <>
              <span className="header-user">{user.username}님</span>
              <button type="button" className="logout-btn" onClick={handleLogout}>
                로그아웃
              </button>
            </>
          ) : (
            <>
              <Link to="/login">로그인</Link>
              <Link to="/register">회원가입</Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
};

export default Header;
