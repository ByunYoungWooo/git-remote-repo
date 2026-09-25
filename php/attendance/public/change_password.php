<?php
/**
 * change_password.php — 비밀번호 변경 (로그인한 모든 사용자)
 */
require_once __DIR__ . '/../src/auth.php';
require_once __DIR__ . '/../src/Layout.php';
require_once __DIR__ . '/../src/Model/Employee.php';

requireLogin();

$msg = $err = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    verifyCsrf();

    $currentPassword = $_POST['current_password'] ?? '';
    $newPassword     = $_POST['new_password'] ?? '';
    $confirmPassword = $_POST['confirm_password'] ?? '';

    // 현재 비밀번호 확인
    $emp = \Employee::findByEmployeeId($_SESSION['user_id']);
    if (!$emp) {
        $err = '계정을 찾을 수 없습니다.';
    } elseif (!password_verify($currentPassword, $emp['password_hash'] ?? '')) {
        $err = '현재 비밀번호가 올바르지 않습니다.';
    } elseif (strlen($newPassword) < 8) {
        $err = '새 비밀번호는 8자 이상이어야 합니다.';
    } elseif ($newPassword !== $confirmPassword) {
        $err = '새 비밀번호와 확인 비밀번호가 일치하지 않습니다.';
    } else {
        \Employee::update((int)$emp['id'], [
            'password_hash' => password_hash($newPassword, PASSWORD_DEFAULT),
        ]);
        $msg = '비밀번호가 변경되었습니다.';
    }
}

layoutHeader('비밀번호 변경', 'profile');
?>
<div class="row justify-content-center">
  <div class="col-md-6">
    <div class="card shadow-sm">
      <div class="card-body p-4">
        <h4 class="mb-3"><i class="bi bi-key me-2"></i>비밀번호 변경</h4>

        <?php if ($msg): ?>
          <div class="alert alert-success py-2"><?= e($msg) ?></div>
        <?php endif; ?>
        <?php if ($err): ?>
          <div class="alert alert-danger py-2"><?= e($err) ?></div>
        <?php endif; ?>

        <form method="post" action="">
          <?= csrfField() ?>
          <div class="mb-3">
            <label class="form-label">현재 비밀번호</label>
            <input type="password" name="current_password" class="form-control" required>
          </div>
          <div class="mb-3">
            <label class="form-label">새 비밀번호 <span class="text-muted">(8자 이상)</span></label>
            <input type="password" name="new_password" class="form-control" minlength="8" required>
          </div>
          <div class="mb-3">
            <label class="form-label">새 비밀번호 확인</label>
            <input type="password" name="confirm_password" class="form-control" minlength="8" required>
          </div>
          <button class="btn btn-primary w-100">비밀번호 변경</button>
        </form>
      </div>
    </div>
    <div class="mt-3 text-center">
      <a href="/clock.php" class="btn btn-outline-secondary btn-sm"><i class="bi bi-arrow-left me-1"></i>돌아가기</a>
    </div>
  </div>
</div>
<?php layoutFooter(); ?>
