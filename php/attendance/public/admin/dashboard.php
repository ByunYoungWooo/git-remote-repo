<?php
/**
 * admin/dashboard.php — 통계 대시보드
 */
require_once __DIR__ . '/../../src/auth.php';
require_once __DIR__ . '/../../src/Layout.php';
require_once __DIR__ . '/../../src/Model/AttendanceLog.php';
require_once __DIR__ . '/../../src/Model/Leave.php';
require_once __DIR__ . '/../../src/Model/Employee.php';
require_once __DIR__ . '/../../src/Model/Holiday.php';

requireRole('admin','manager');

$ym = $_GET['ym'] ?? date('Y-m');
$stats = AttendanceLog::stats($ym);
$byEmp = AttendanceLog::statsByEmployee($ym);
$pending = Leave::pending();
$holidayCount = count(Holiday::forYear((int)$ym . '' === '' ? date('Y') : (int)substr($ym,0,4)));

// 평균 출근 시간
$stmt = getDB()->prepare(
    'SELECT AVG(TIME_TO_SEC(time_in))/3600 AS avg_in FROM attendance_logs
     WHERE time_in IS NOT NULL AND check_date BETWEEN ? AND ?'
);
$start = $ym . '-01';
$end   = date('Y-m-t', strtotime($start));
$stmt->execute([$start, $end]);
$avgIn = $stmt->fetchColumn();
$avgInStr = $avgIn ? sprintf('%02d:%02d', (int)$avgIn, (int)round((($avgIn - (int)$avgIn) * 60))) : '-';

layoutHeader('관리자 대시보드', 'admin');
?>
<div class="d-flex justify-content-between align-items-center mb-4">
  <h4 class="mb-0"><i class="bi bi-speedometer2 me-2"></i>통계 대시보드</h4>
  <form method="get" class="d-flex gap-2">
    <input type="month" name="ym" class="form-control form-control-sm" value="<?= e($ym) ?>" required>
    <button class="btn btn-primary btn-sm">조회</button>
  </form>
</div>

<div class="row g-3 mb-4">
  <div class="col-6 col-lg-3">
    <div class="card text-center">
      <div class="card-body py-3">
        <h6 class="text-muted">총 출석 기록</h6>
        <div class="display-6 fw-bold"><?= (int)($stats['total'] ?? 0) ?></div>
      </div>
    </div>
  </div>
  <div class="col-6 col-lg-3">
    <div class="card text-center border-success">
      <div class="card-body py-3">
        <h6 class="text-muted">정상 출석</h6>
        <div class="display-6 fw-bold text-success"><?= (int)($stats['present_count'] ?? 0) ?></div>
      </div>
    </div>
  </div>
  <div class="col-6 col-lg-3">
    <div class="card text-center border-warning">
      <div class="card-body py-3">
        <h6 class="text-muted">지각</h6>
        <div class="display-6 fw-bold text-warning"><?= (int)($stats['late_count'] ?? 0) ?></div>
      </div>
    </div>
  </div>
  <div class="col-6 col-lg-3">
    <div class="card text-center border-danger">
      <div class="card-body py-3">
        <h6 class="text-muted">결석/조퇴</h6>
        <div class="display-6 fw-bold text-danger"><?= (int)($stats['absent_count'] ?? 0) + (int)($stats['early_count'] ?? 0) ?></div>
      </div>
    </div>
  </div>
</div>

<div class="row g-4">
  <div class="col-lg-8">
    <div class="card shadow-sm">
      <div class="card-header bg-white fw-bold">직원별 출석 현황 (<?= e($ym) ?>)</div>
      <div class="table-responsive">
        <table class="table table-sm mb-0">
          <thead><tr><th>이름</th><th>부서</th><th>출석일</th><th>지각</th><th>결석</th><th>조퇴</th></tr></thead>
          <tbody>
            <?php foreach ($byEmp as $r): ?>
            <tr>
              <td><?= e($r['name']) ?></td>
              <td><?= e($r['department'] ?? '-') ?></td>
              <td><?= (int)$r['days'] ?></td>
              <td class="<?= $r['late'] ? 'text-warning fw-bold' : '' ?>"><?= (int)$r['late'] ?></td>
              <td class="<?= $r['absent'] ? 'text-danger fw-bold' : '' ?>"><?= (int)$r['absent'] ?></td>
              <td><?= (int)$r['early'] ?></td>
            </tr>
            <?php endforeach; ?>
          </tbody>
        </table>
      </div>
    </div>
  </div>
  <div class="col-lg-4">
    <div class="card shadow-sm mb-3">
      <div class="card-body text-center">
        <h6 class="text-muted">평균 출근 시간</h6>
        <div class="display-5 fw-bold"><?= e($avgInStr) ?></div>
      </div>
    </div>
    <div class="card shadow-sm">
      <div class="card-header bg-white fw-bold text-warning">승인 대기 연차</div>
      <ul class="list-group list-group-flush">
        <?php foreach ($pending as $p): ?>
        <li class="list-group-item">
          <strong><?= e($p['employee_name']) ?></strong>
          <span class="text-muted small">
            <?= e($p['start_date']) ?>~<?= e($p['end_date']) ?> (<?= (int)$p['duration_days'] ?>일)
          </span>
          <a href="leaves.php" class="badge bg-warning text-dark float-end">처리</a>
        </li>
        <?php endforeach; ?>
        <?php if (!$pending): ?><li class="list-group-item text-muted">대기 없음</li><?php endif; ?>
      </ul>
    </div>
  </div>
</div>

<nav class="mt-4">
  <ul class="nav nav-pills flex-wrap gap-1">
    <li><a class="nav-link" href="employees.php">직원 관리</a></li>
    <li><a class="nav-link" href="attendance.php">출석 검토</a></li>
    <li><a class="nav-link" href="calendar.php">캘린더 관리</a></li>
    <li><a class="nav-link" href="leaves.php">연차 관리</a></li>
    <li><a class="nav-link" href="reports.php">보고서</a></li>
  </ul>
</nav>
<?php layoutFooter(); ?>
