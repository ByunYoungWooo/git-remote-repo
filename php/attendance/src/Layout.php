<?php
/**
 * Layout — 공통 레이아웃 헬퍼
 */
require_once __DIR__ . '/auth.php';

function layoutHeader(string $title, string $active = ''): void
{
    $user = currentUserName() ?? '게스트';
    $role = currentUserRole() ?? '';
    $navItems = [
        ''           => ['label' => '홈', 'href' => '/index.php'],
        'clock'      => ['label' => '출퇴근 체크', 'href' => '/clock.php'],
        'leaves'     => ['label' => '연차', 'href' => '/leaves.php'],
        'calendar'   => ['label' => '캘린더', 'href' => '/calendar.php'],
    ];
    if (isLoggedIn()) {
        $navItems['password'] = ['label' => '비밀번호 변경', 'href' => '/change_password.php'];
    }
    if (in_array($role, ['admin','manager'], true)) {
        $navItems['admin'] = ['label' => '어드민', 'href' => '/admin/'];
    }
    $nav = '';
    foreach ($navItems as $key => $item) {
        $cls = ($active === $key) ? ' active' : '';
        $nav .= '<li class="nav-item"><a class="nav-link' . $cls . '" href="' . $item['href'] . '">' . $item['label'] . '</a></li>';
    }
    ?>
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title><?= e($title) ?> — 출석관리 Pro</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">
</head>
<body class="bg-light min-vh-100">
<nav class="navbar navbar-expand-lg navbar-dark bg-primary mb-4">
  <div class="container">
    <a class="navbar-brand fw-bold" href="/index.php">출석관리 Pro</a>
    <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#nav">
      <span class="navbar-toggler-icon"></span>
    </button>
    <div class="collapse navbar-collapse" id="nav">
      <ul class="navbar-nav me-auto"><?= $nav ?></ul>
      <span class="navbar-text me-3">
        <i class="bi bi-person"></i> <?= e($user) ?>
        <?php if ($role): ?><span class="badge bg-light text-dark ms-1"><?= e($role) ?></span><?php endif; ?>
      </span>
      <a href="/logout.php" class="btn btn-outline-light btn-sm">로그아웃</a>
    </div>
  </div>
</nav>
<main class="container pb-5">
    <?php
}

function layoutFooter(): void
{
    ?>
</main>
<footer class="text-center text-muted py-3 bg-white border-top">
  <small>출석관리 Pro &copy; 2026</small>
</footer>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
    <?php
}
