<?php
require_once __DIR__ . '/../src/auth.php';
require_once __DIR__ . '/../src/Layout.php';
require_once __DIR__ . '/../src/Model/Employee.php';
require_once __DIR__ . '/../src/Model/AttendanceLog.php';
require_once __DIR__ . '/../src/Model/Holiday.php';

requireLogin();

$msg = $err = '';
$today = date('Y-m-d');
$emp = Employee::findByEmployeeId($_SESSION['user_id'] ?? '');

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    verifyCsrf();
    $action = $_POST['action'] ?? '';
    $result = AttendanceLog::check($_SESSION['user_id'], $today, $action === 'in', $_POST['reason'] ?? null);
    if (!empty($result['ok'])) {
        $msg = $result['message'];
    } else {
        $err = $result['error'] ?? '에러';
    }
}

$todayRow = null;
if ($emp) {
    $stmt = getDB()->prepare('SELECT * FROM attendance_logs WHERE employee_id = ? AND check_date = ?');
    $stmt->execute([$_SESSION['user_id'], $today]);
    $todayRow = $stmt->fetch();
}
$isHoliday = Holiday::isHoliday($today);

layoutHeader('출퇴근 체크', 'clock');
?>
<div class="row g-4">
  <div class="col-md-7">
    <div class="card shadow-sm">
      <div class="card-body p-4">
        <h4 class="mb-1"><?= e($emp['name'] ?? '') ?></h4>
        <p class="text-muted mb-3"><?= $today ?>
          <?php if ($isHoliday): ?><span class="badge bg-danger">공휴일: <?= e($isHoliday['holiday_name']) ?></span><?php endif; ?>
        </p>

        <?php if ($msg): ?><div class="alert alert-success py-2"><?= e($msg) ?></div><?php endif; ?>
        <?php if ($err): ?><div class="alert alert-danger py-2"><?= e($err) ?></div><?php endif; ?>

        <div class="row g-3">
          <div class="col-6">
            <?php if ($todayRow && $todayRow['time_in']): ?>
              <div class="text-center p-3 bg-success bg-opacity-10 rounded">
                <div class="text-success fw-bold text-3xl"><i class="bi bi-clock me-2"></i><?= e(substr($todayRow['time_in'],0,5)) ?></div>
                <small>출근 완료</small>
              </div>
            <?php else: ?>
              <form method="post" action="">
                <?= csrfField() ?>
                <input type="hidden" name="action" value="in">
                <div class="mb-2">
                  <input type="text" name="reason" class="form-control form-control-sm" placeholder="사유 (선택)">
                </div>
                <button class="btn btn-success w-100 fw-bold"><i class="bi bi-box-arrow-in-right me-1"></i>출근 체크</button>
              </form>
            <?php endif; ?>
          </div>
          <div class="col-6">
            <?php if ($todayRow && $todayRow['time_out']): ?>
              <div class="text-center p-3 bg-secondary bg-opacity-10 rounded">
                <div class="text-secondary fw-bold text-3xl"><i class="bi bi-clock me-2"></i><?= e(substr($todayRow['time_out'],0,5)) ?></div>
                <small>퇴근 완료</small>
              </div>
            <?php elseif ($todayRow && $todayRow['time_in']): ?>
              <form method="post" action="">
                <?= csrfField() ?>
                <input type="hidden" name="action" value="out">
                <div class="mb-2">
                  <input type="text" name="reason" class="form-control form-control-sm" placeholder="사유 (선택)">
                </div>
                <button class="btn btn-secondary w-100 fw-bold"><i class="bi bi-box-arrow-left me-1"></i>퇴근 체크</button>
              </form>
            <?php else: ?>
              <div class="text-center p-3 bg-light rounded text-muted">
                <small>출근 후 사용 가능</small>
              </div>
            <?php endif; ?>
          </div>
        </div>

        <?php if ($emp): ?>
        <hr>
        <div class="d-flex justify-content-between text-muted small">
          <span>기준 출근: <?= e(substr($emp['attendance_time_in'] ?? '09:00', 0, 5)) ?></span>
          <span>기준 퇴근: <?= e(substr($emp['attendance_time_out'] ?? '18:00', 0, 5)) ?></span>
        </div>
        <?php endif; ?>
      </div>
    </div>
  </div>

  <div class="col-md-5">
    <div class="card shadow-sm">
      <div class="card-header bg-white fw-bold">최근 출석 기록</div>
      <div class="table-responsive">
        <table class="table table-sm mb-0">
          <thead><tr><th>날짜</th><th>출근</th><th>퇴근</th><th>상태</th></tr></thead>
          <tbody>
            <?php
            $stmt = getDB()->prepare('SELECT * FROM attendance_logs WHERE employee_id = ? ORDER BY check_date DESC LIMIT 10');
            $stmt->execute([$_SESSION['user_id']]);
            $statusMap = ['present'=>'성공', 'late'=>'지각', 'absent'=>'결석', 'early_leave'=>'조퇴'];
            foreach ($stmt as $r): ?>
              <tr>
                <td><?= e($r['check_date']) ?></td>
                <td><?= e($r['time_in'] ? substr($r['time_in'],0,5) : '-') ?></td>
                <td><?= e($r['time_out'] ? substr($r['time_out'],0,5) : '-') ?></td>
                <td><span class="badge bg-<?= $r['status']==='late'?'warning text-dark':'light' ?>"><?= $statusMap[$r['status']] ?? $r['status'] ?></span></td>
              </tr>
            <?php endforeach; ?>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>
<?php layoutFooter(); ?>
