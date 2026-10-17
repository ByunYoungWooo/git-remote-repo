import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import './Login.css';
import { login as apiLogin } from '../services/auth';
import { saveSession } from '../services/api';

const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      setError('이메일과 비밀번호를 입력해주세요.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const data = await apiLogin({ email, password });
      saveSession(data.token, { id: data.userId, username: data.username, email });
      navigate('/products');
    } catch (err) {
      setError(err.response?.data?.error || '로그인 실패. 이메일 또는 비밀번호를 확인해주세요.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-wrap">
      <form onSubmit={handleSubmit} className="auth-form login-form">
        <h1>로그인</h1>
        {error && <div className="error-message">{error}</div>}
        <div className="form-group">
          <label htmlFor="email">이메일</label>
          <input type="email" id="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className="form-group">
          <label htmlFor="password">비밀번호</label>
          <input type="password" id="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        <button type="submit" className="primary-button" disabled={loading}>
          {loading ? '로그인 중...' : '로그인'}
        </button>
        <div className="auth-links">
          <span>아직 회원이 아니신가요? </span>
          <Link to="/register">회원가입</Link>
        </div>
      </form>
    </div>
  );
};

export default Login;
