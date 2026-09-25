<?php
require_once __DIR__ . '/../src/auth.php';
require_once __DIR__ . '/../src/Layout.php';
require_once __DIR__ . '/../src/Model/Employee.php';

if (isLoggedIn()) {
    header('Location: clock.php');
    exit;
}

$err = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $username = trim($_POST['username'] ?? '');
    $password = $_POST['password'] ?? '';
    if ($username !== '' && $password !== '') {
        $emp = \Employee::findByLogin($username);
        if ($emp && password_verify($password, $emp['password_hash'] ?? '')) {
            doLogin($emp['employee_id'], $emp['name'], $emp['role'] ?? 'employee');
            header('Location: clock.php');
            exit;
        }
        $err = '아이디 또는 비밀번호가 올바르지 않습니다.';
    }
}
?>
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>로그인 — 출석관리 Pro</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">
<style>
  html, body { height: 100%; }
  .login-stage {
    min-height: 100vh;
    display: flex; align-items: center; justify-content: center;
    padding: 24px;
    background: #1e3a8a url("assets/login-bg.svg") center / cover no-repeat, linear-gradient(135deg,#0f1b4c,#1e3a8a);
    position: relative; overflow: hidden;
  }
  .login-stage::after {
    content: ""; position: absolute; inset: 0;
    background: radial-gradient(circle at 72% 38%, rgba(9,20,51,.0), rgba(9,20,51,.45) 75%);
    pointer-events: none;
  }
  .login-card {
    width: 100%; max-width: 420px; position: relative; z-index: 1;
    background: rgba(255,255,255,.94);
    border-radius: 20px;
    box-shadow: 0 24px 64px rgba(3,10,38,.45), 0 0 0 1px rgba(255,255,255,.35) inset;
    backdrop-filter: blur(8px);
    animation: rise .45s ease both;
  }
  @keyframes rise { from { opacity: 0; transform: translateY(18px);} to { opacity: 1; transform: none;} }
  .login-brand { text-align: center; margin-bottom: 22px; }
  .login-logo {
    width: 64px; height: 64px; border-radius: 18px; margin: 0 auto 12px;
    background: linear-gradient(135deg,#2563eb,#1e3a8a);
    color: #fff; display:flex; align-items:center; justify-content:center; font-size: 1.9rem;
    box-shadow: 0 10px 24px rgba(37,99,235,.4);
  }
  .login-title { margin: 0; font-weight: 800; font-size: 1.35rem; color:#0f1b4c;}
  .login-sub { font-size: .86rem; color:#64748b; margin-top: 4px; }
  .form-control:focus, .btn-login:focus { box-shadow: 0 0 0 .25rem rgba(37,99,235,.18); border-color:#2563eb;}
  .btn-login {
    background: linear-gradient(135deg,#2563eb,#1d4ed8);
    color:#fff; font-weight:700; border:none; padding:.7rem 0;
  }
  .btn-login:hover { filter: brightness(1.08); color:#fff;}
  .login-foot { position:absolute; bottom: 18px; left:0; right:0; text-align:center; z-index:1; }
  .login-foot small { color: rgba(255,255,255,.75); letter-spacing:.4px;}
</style>
</head>
<body>
<div class="login-stage">
  <div class="login-card p-4 p-md-5">
    <div class="login-brand">
      <div class="login-logo"><i class="bi bi-clock-history"></i></div>
      <h1 class="login-title">출석관리 Pro</h1>
      <p class="login-sub">로그인하고 오늘도 출근 체크하세요</p>
    </div>

    <?php if ($err): ?>
      <div class="alert alert-danger py-2" style="border-radius:12px;"><?= e($err) ?></div>
    <?php endif; ?>

    <form method="post" action="">
      <div class="mb-3">
        <label class="form-label small fw-semibold text-secondary">아이디</label>
        <input type="text" name="username" class="form-control form-control-lg" placeholder="로그인 아이디" required autofocus>
      </div>
      <div class="mb-4">
        <label class="form-label small fw-semibold text-secondary">비밀번호</label>
        <input type="password" name="password" class="form-control form-control-lg" placeholder="비밀번호" required>
      </div>
      <button class="btn btn-login w-100">로그인</button>
    </form>
  </div>

  <div class="login-foot"><small>출석관리 Pro &copy; 2026</small></div>
</div>
</body>
</html>
