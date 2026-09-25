<?php
/**
 * admin/reports.php — 보고서
 */
require_once __DIR__ . '/../../src/auth.php';
require_once __DIR__ . '/../../src/Layout.php';
require_once __DIR__ . '/../../src/Model/AttendanceLog.php';
require_once __DIR__ . '/../../src/Model/Employee.php';
require_once __DIR__ . '/../../src/Model/Leave.php';

requireRole('admin','manager');

$month = $_GET['month'] ?? date('Y-m');
$year  = (int)substr($month, 0, 4);
$stats = AttendanceLog::stats($month);
$byEmp = AttendanceLog::statsByEmployee($month);

// 월별 추이 (최근 6개월)
$months = [];
for ($i = 5; $i >= 0; $i--) {
    $ts = strtotime("first day of -{$i} months");
    $months[] = date('Y-m', $ts);
}
$monthlyTrend = [];
foreach ($months as $m) {
    $s = AttendanceLog::stats($m);
    $total = (int)($s['total'] ?? 0);
    $late  = (int)($s['late_count'] ?? 0);
    $absent= (int)($s['absent_count'] ?? 0);
    $early = (int)($s['early_count'] ?? 0);
    $present = (int)($s['present_count'] ?? 0);
    $monthlyTrend[] = [
        'month'   => $m,
        'label'   => (int)date('n', strtotime($m)) . '월',
        'total'   => $total,
        'present' => $present,
        'late'    => $late,
        'absent'  => $absent,
        'early'   => $early,
        'rate'    => $total > 0 ? round($present / $total * 100, 1) : 0,
    ];
}

// CSV 내보내기
if (isset($_GET['export'])) {
    $rows = getDB()->prepare(
        'SELECT e.name, e.department, al.check_date, al.time_in, al.time_out, al.status, al.reason
         FROM attendance_logs al JOIN employees e ON e.employee_id = al.employee_id
         WHERE al.check_date BETWEEN ? AND ?
         ORDER BY al.check_date, e.name'
    );
    $start = $month . '-01';
    $end   = date('Y-m-t', strtotime($start));
    $rows->execute([$start, $end]);
    $all = $rows->fetchAll();

    header('Content-Type: text/csv; charset=utf-8');
    header('Content-Disposition: attachment; filename="attendance_' . $month . '.csv"');
    echo "\xEF\xBB\xBF";
    $out = fopen('php://output', 'w');
    fputcsv($out, ['이름','부서','날짜','출근','퇴근','상태','사유']);
    $statusMap = ['present'=>'정상','late'=>'지각','absent'=>'결근','early_leave'=>'조퇴'];
    foreach ($all as $r) {
        fputcsv($out, [
            $r['name'], $r['department'], $r['check_date'],
            substr($r['time_in'] ?? '', 0, 5), substr($r['time_out'] ?? '', 0, 5),
            $statusMap[$r['status']] ?? $r['status'], $r['reason'] ?? ''
        ]);
    }
    fclose($out);
    exit;
}

layoutHeader('보고서', 'reports');
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <h5>월별 출근 보고서</h5>
  <div class="d-flex gap-2">
    <form method="get" class="d-flex gap-1">
      <input type="month" name="month" value="<?= e($month) ?>" class="form-control form-control-sm">
      <button class="btn btn-sm btn-primary">조회</button>
      <a href="?month=<?= e($month) ?>&export=1" class="btn btn-sm btn-outline-success">CSV 내보내기</a>
    </form>
  </div>
</div>

<div class="row g-3 mb-3">
  <div class="col">
    <div class="card shadow-sm"><div class="card-body text-center py-3">
      <div class="text-muted small">총 출근일수</div>
      <div class="fs-2 fw-bold"><?= (int)($stats['total'] ?? 0) ?></div>
    </div></div>
  </div>
  <div class="col">
    <div class="card shadow-sm"><div class="card-body text-center py-3">
      <div class="text-muted small">정상 출근</div>
      <div class="fs-2 fw-bold text-success"><?= (int)($stats['present_count'] ?? 0) ?></div>
    </div></div>
  </div>
  <div class="col">
    <div class="card shadow-sm"><div class="card-body text-center py-3">
      <div class="text-muted small">지각</div>
      <div class="fs-2 fw-bold text-warning"><?= (int)($stats['late_count'] ?? 0) ?></div>
    </div></div>
  </div>
  <div class="col">
    <div class="card shadow-sm"><div class="card-body text-center py-3">
      <div class="text-muted small">결근</div>
      <div class="fs-2 fw-bold text-danger"><?= (int)($stats['absent_count'] ?? 0) ?></div>
    </div></div>
  </div>
  <div class="col">
    <div class="card shadow-sm"><div class="card-body text-center py-3">
      <div class="text-muted small">조퇴</div>
      <div class="fs-2 fw-bold text-secondary"><?= (int)($stats['early_count'] ?? 0) ?></div>
    </div></div>
  </div>
</div>

<div class="row g-4">
  <div class="col-md-7">
    <div class="card shadow-sm">
      <div class="card-header bg-white fw-bold">직별 출근 현황 (<?= e($month) ?>)</div>
      <div class="table-responsive">
        <table class="table table-sm table-hover mb-0">
          <thead><tr><th>이름</th><th>부서</th><th>출근일수</th><th>지각</th><th>결근</th><th>조퇴</th></tr></thead>
          <tbody>
            <?php foreach ($byEmp as $r): ?>
            <tr>
              <td class="fw-bold"><?= e($r['name']) ?></td>
              <td><?= e($r['department']) ?></td>
              <td class="fw-bold"><?= (int)($r['days'] ?? 0) ?></td>
              <td><?php $late = (int)($r['late'] ?? 0); ?><?= $late ? "<span class='badge bg-warning text-dark'>{$late}</span>" : '<span class="text-muted">0</span>' ?></td>
              <td><?php $abs = (int)($r['absent'] ?? 0); ?><?= $abs ? "<span class='badge bg-danger'>{$abs}</span>" : '<span class="text-muted">0</span>' ?></td>
              <td><?php $early = (int)($r['early'] ?? 0); ?><?= $early ? "<span class='badge bg-secondary'>{$early}</span>" : '<span class="text-muted">0</span>' ?></td>
            </tr>
            <?php endforeach; ?>
            <?php if (empty($byEmp)): ?><tr><td colspan="6" class="text-center text-muted py-3">데이터가 없습니다</td></tr><?php endif; ?>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <div class="col-md-5">
    <div class="card shadow-sm">
      <div class="card-header bg-white fw-bold">최근 6개월 추이</div>
      <div class="table-responsive">
        <table class="table table-sm mb-0">
          <thead><tr><th>월</th><th>출근</th><th>정상</th><th>지각</th><th>결근</th><th>조퇴</th><th>출근율</th></tr></thead>
          <tbody>
            <?php foreach ($monthlyTrend as $t): ?>
            <tr class="<?= $t['month'] === $month ? 'table-primary' : '' ?>">
              <td class="fw-bold"><?= e($t['label']) ?></td>
              <td><?= (int)$t['total'] ?></td>
              <td class="text-success"><?= (int)$t['present'] ?></td>
              <td class="text-warning"><?= (int)$t['late'] ?></td>
              <td class="text-danger"><?= (int)$t['absent'] ?></td>
              <td class="text-secondary"><?= (int)$t['early'] ?></td>
              <td>
                <?php $rate = (float)$t['rate']; ?>
                <div class="progress" style="height:18px; min-width:80px;">
                  <div class="progress-bar bg-<?= $rate >= 95 ? 'success' : ($rate >= 80 ? 'warning' : 'danger') ?>"
                       style="width:<?= min(100, $rate) ?>%"><?= $rate ?>%</div>
                </div>
              </td>
            </tr>
            <?php endforeach; ?>
          </tbody>
        </table>
      </div>
    </div>

    <div class="card shadow-sm mt-3">
      <div class="card-header bg-white fw-bold">요약</div>
      <div class="card-body">
        <?php
        $totalAll = array_sum(array_map(fn($t) => $t['total'], $monthlyTrend));
        $presentAll = array_sum(array_map(fn($t) => $t['present'], $monthlyTrend));
        $lateAll = array_sum(array_map(fn($t) => $t['late'], $monthlyTrend));
        $absentAll = array_sum(array_map(fn($t) => $t['absent'], $monthlyTrend));
        $earlyAll = array_sum(array_map(fn($t) => $t['early'], $monthlyTrend));
        $overallRate = $totalAll > 0 ? round($presentAll / $totalAll * 100, 1) : 0;
        ?>
        <table class="table table-sm mb-0">
          <tbody>
            <tr><td>6개월 총 출근</td><td class="text-end fw-bold"><?= $totalAll ?></td></tr>
            <tr><td>정상 출근</td><td class="text-end text-success fw-bold"><?= $presentAll ?></td></tr>
            <tr><td>지각 합계</td><td class="text-end text-warning fw-bold"><?= $lateAll ?></td></tr>
            <tr><td>결근 합계</td><td class="text-end text-danger fw-bold"><?= $absentAll ?></td></tr>
            <tr><td>조퇴 합계</td><td class="text-end text-secondary fw-bold"><?= $earlyAll ?></td></tr>
            <tr><td><strong>종합 출근율</strong></td><td class="text-end"><strong class="fs-5 <?= $overallRate >= 95 ? 'text-success' : ($overallRate >= 80 ? 'text-warning' : 'text-danger') ?>"><?= $overallRate ?>%</strong></td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>
<?php layoutFooter(); ?>
