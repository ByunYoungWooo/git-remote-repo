import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import './Register.css';
import { register as apiRegister } from '../services/auth';

const Register = () => {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username || !email || !password) {
      setError('모든 항목을 입력해주세요.');
      return;
    }
    if (password.length < 8) {
      setError('비밀번호는 8자 이상이어야 합니다.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await apiRegister({ username, email, password });
      setSuccess(true);
      setTimeout(() => navigate('/login'), 1200);
    } catch (err) {
      setError(err.response?.data?.error || '회원가입에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="auth-wrap">
        <div className="auth-form auth-success">
          <h1>회원가입 완료</h1>
          <p>로그인 페이지로 이동합니다.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-wrap">
      <form onSubmit={handleSubmit} className="auth-form register-form">
        <h1>회원가입</h1>
        {error && <div className="error-message">{error}</div>}
        <div className="form-group">
          <label htmlFor="username">닉네임</label>
          <input id="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
        </div>
        <div className="form-group">
          <label htmlFor="reg-email">이메일</label>
          <input type="email" id="reg-email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className="form-group">
          <label htmlFor="reg-password">비밀번호</label>
          <input type="password" id="reg-password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} required />
        </div>
        <button type="submit" className="primary-button" disabled={loading}>
          {loading ? '가입 중...' : '회원가입'}
        </button>
        <div className="auth-links">
          <span>이미 회원이신가요? </span>
          <Link to="/login">로그인</Link>
        </div>
      </form>
    </div>
  );
};

export default Register;
