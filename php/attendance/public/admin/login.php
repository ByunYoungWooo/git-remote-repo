<?php
/**
 * admin/login.php — 관리자 로그인
 */
require_once __DIR__ . '/../../src/auth.php';
require_once __DIR__ . '/../../src/Layout.php';
require_once __DIR__ . '/../../src/Model/Employee.php';

if (isLoggedIn() && in_array(currentUserRole(), ['admin','manager'], true)) {
    header('Location: dashboard.php');
    exit;
}

$err = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $username = trim($_POST['username'] ?? '');
    $password = $_POST['password'] ?? '';
    if ($username !== '' && $password !== '') {
        $emp = Employee::findByLogin($username);
        if ($emp && password_verify($password, $emp['password_hash'] ?? '')
            && in_array($emp['role'] ?? '', ['admin','manager'], true)) {
            doLogin($emp['employee_id'], $emp['name'], $emp['role']);
            header('Location: dashboard.php');
            exit;
        }
        $err = '관리자 계정이 아니거나 인증에 실패했습니다.';
    }
}

layoutHeader('관리자 로그인', 'admin');
?>
<div class="row justify-content-center">
  <div class="col-md-5">
    <div class="card shadow">
      <div class="card-body p-4">
        <h4 class="mb-3"><i class="bi bi-shield-lock me-2"></i>관리자 로그인</h4>
        <?php if ($err): ?><div class="alert alert-danger py-2"><?= e($err) ?></div><?php endif; ?>
        <form method="post" action="">
          <div class="mb-3">
            <label class="form-label">아이디</label>
            <input type="text" name="username" class="form-control" required autofocus>
          </div>
          <div class="mb-3">
            <label class="form-label">비밀번호</label>
            <input type="password" name="password" class="form-control" required>
          </div>
          <button class="btn btn-dark w-100">로그인</button>
          <a href="../index.php" class="d-block text-center mt-2 small text-muted">일반 로그인으로 돌아가기</a>
        </form>
      </div>
    </div>
  </div>
</div>
<?php layoutFooter(); ?>
