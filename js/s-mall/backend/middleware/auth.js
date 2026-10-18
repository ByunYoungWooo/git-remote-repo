// JWT 인증 미들웨어
const jwt = require('jsonwebtoken');
const { getSecret } = require('../config/jwt');

module.exports = function authRequired(req, res, next) {
  const header = req.headers.authorization || '';
  const token = header.startsWith('Bearer ') ? header.slice(7) : null;

  if (!token) {
    return res.status(401).json({ error: '토큰이 필요합니다.' });
  }

  try {
    const decoded = jwt.verify(token, getSecret());
    req.userId = decoded.userId;
    req.username = decoded.username;
    next();
  } catch (err) {
    return res.status(401).json({ error: '유효하지 않은 토큰입니다.' });
  }
};
