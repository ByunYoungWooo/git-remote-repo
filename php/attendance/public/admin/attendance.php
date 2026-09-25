<?php
/**
 * admin/attendance.php — 출석 검토
 */
require_once __DIR__ . '/../../src/auth.php';
require_once __DIR__ . '/../../src/Layout.php';
require_once __DIR__ . '/../../src/Model/AttendanceLog.php';
require_once __DIR__ . '/../../src/Model/Employee.php';

requireRole('admin','manager');

$date = $_GET['date'] ?? date('Y-m-d');
$logs = AttendanceLog::forDate($date);
$employees = Employee::all();
$statusMap = ['present'=>'정상','late'=>'지각','absent'=>'결근','early_leave'=>'조퇴'];
$statusClass = ['present'=>'success','late'=>'warning text-dark','absent'=>'danger','early_leave'=>'secondary'];

// 결근자 계산: 해당 날짜에 로그가 없는 직원
$logEmpIds = array_column($logs, 'employee_id');
$absentees = array_filter($employees, fn($e) => !in_array($e['employee_id'], $logEmpIds) && $e['role'] === 'employee');

// 출석 기록 수정 (admin 권한)
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    verifyCsrf();
    $action = $_POST['action'] ?? '';
    $targetDate = $_POST['date'] ?? $date;

    if ($action === 'correct') {
        $empId = $_POST['employee_id'] ?? '';
        $field = $_POST['field'] ?? ''; // time_in / time_out
        $val = $_POST['value'] ?? '';
        if ($empId && $field && $val) {
            $col = $field === 'time_in' ? 'time_in' : 'time_out';
            $stmt = getDB()->prepare("UPDATE attendance_logs SET {$col} = ? WHERE employee_id = ? AND check_date = ?");
            $stmt->execute([$val, $empId, $targetDate]);
            $date = $targetDate;
            $logs = AttendanceLog::forDate($date);
        }
    } elseif ($action === 'add_absent') {
        $empId = $_POST['employee_id'] ?? '';
        if ($empId) {
            $stmt = getDB()->prepare(
                'INSERT INTO attendance_logs (employee_id, check_date, status, auto_checked)
                 VALUES (?,?,?,0)
                 ON DUPLICATE KEY UPDATE status = VALUES(status)'
            );
            $stmt->execute([$empId, $targetDate, 'absent']);
            $date = $targetDate;
            $logs = AttendanceLog::forDate($date);
        }
    }
}

layoutHeader('출석 검토', 'attendance');
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <h5>출석 검토</h5>
  <form method="get" class="d-flex gap-2">
    <input type="date" name="date" value="<?= e($date) ?>" class="form-control form-control-sm">
    <button class="btn btn-primary btn-sm">조회</button>
  </form>
</div>

<div class="row g-3 mb-3">
  <div class="col">
    <div class="card text-bg-success shadow-sm"><div class="card-body py-2 fw-bold">정상 <?= count(array_filter($logs, fn($l) => $l['status']==='present')) ?>명</div></div>
  </div>
  <div class="col">
    <div class="card text-bg-warning shadow-sm"><div class="card-body py-2 fw-bold">지각 <?= count(array_filter($logs, fn($l) => $l['status']==='late')) ?>명</div></div>
  </div>
  <div class="col">
    <div class="card text-bg-danger shadow-sm"><div class="card-body py-2 fw-bold">결근 <?= count($absentees) ?>명</div></div>
  </div>
  <div class="col">
    <div class="card text-bg-secondary shadow-sm"><div class="card-body py-2 fw-bold">조퇴 <?= count(array_filter($logs, fn($l) => $l['status']==='early_leave')) ?>명</div></div>
  </div>
</div>

<div class="card shadow-sm mb-3">
  <div class="card-header bg-white fw-bold"><?= e($date) ?> 출석 현황</div>
  <div class="table-responsive">
    <table class="table table-sm table-hover mb-0">
      <thead><tr><th>이름</th><th>부서</th><th>출근</th><th>퇴근</th><th>상태</th><th>사유</th><th>수정</th></tr></thead>
      <tbody>
        <?php foreach ($logs as $l): ?>
        <tr>
          <td class="fw-bold"><?= e($l['name']) ?></td>
          <td><?= e($l['department']) ?></td>
          <td>
            <?php if ($l['time_in']): ?>
              <span class="text-success fw-bold"><?= e(substr($l['time_in'],0,5)) ?></span>
              <?php if ($l['expected_in'] && substr($l['time_in'],0,5) > substr($l['expected_in'],0,5)): ?>
                <small class="text-muted">(예상 <?= e(substr($l['expected_in'],0,5)) ?>)</small>
              <?php endif; ?>
            <?php else: ?><span class="text-muted">-</span><?php endif; ?>
          </td>
          <td>
            <?php if ($l['time_out']): ?>
              <span class="text-primary fw-bold"><?= e(substr($l['time_out'],0,5)) ?></span>
              <?php if ($l['expected_out'] && substr($l['time_out'],0,5) < substr($l['expected_out'],0,5)): ?>
                <small class="text-muted">(예상 <?= e(substr($l['expected_out'],0,5)) ?>)</small>
              <?php endif; ?>
            <?php else: ?><span class="text-muted">-</span><?php endif; ?>
          </td>
          <td><span class="badge bg-<?= $statusClass[$l['status']] ?? 'secondary' ?>"><?= $statusMap[$l['status']] ?? e($l['status']) ?></span></td>
          <td><?= e($l['reason'] ?? '') ?: '-' ?></td>
          <td>
            <?php if ($l['time_in'] && !$l['time_out']): ?>
            <form method="post" class="d-flex gap-1 align-items-center">
              <?= csrfField() ?>
              <input type="hidden" name="date" value="<?= e($date) ?>">
              <input type="hidden" name="action" value="correct">
              <input type="hidden" name="employee_id" value="<?= e($l['employee_id']) ?>">
              <input type="hidden" name="field" value="time_out">
              <input type="time" name="value" placeholder="18:00" class="form-control form-control-sm" style="width:100px">
              <button class="btn btn-sm btn-outline-primary">퇴근수정</button>
            </form>
            <?php endif; ?>
          </td>
        </tr>
        <?php endforeach; ?>
        <?php if (empty($logs)): ?><tr><td colspan="7" class="text-center text-muted py-3">기록이 없습니다</td></tr><?php endif; ?>
      </tbody>
    </table>
  </div>
</div>

<div class="card shadow-sm">
  <div class="card-header bg-white fw-bold">결근 등록 (<?= e($date) ?>)</div>
  <div class="card-body">
    <?php if (empty($absentees)): ?>
      <p class="text-muted mb-0">결근자가 없습니다. 모든 직원이 출석 기록을 보유하고 있습니다.</p>
    <?php else: ?>
      <form method="post" class="d-flex gap-2 align-items-center">
        <?= csrfField() ?>
        <input type="hidden" name="date" value="<?= e($date) ?>">
        <input type="hidden" name="action" value="add_absent">
        <select name="employee_id" class="form-select form-select-sm" style="max-width:200px">
          <?php foreach ($absentees as $a): ?>
            <option value="<?= e($a['employee_id']) ?>"><?= e($a['name']) ?> (<?= e($a['department']) ?>)</option>
          <?php endforeach; ?>
        </select>
        <button class="btn btn-sm btn-outline-danger">결근 처리</button>
      </form>
    <?php endif; ?>
  </div>
</div>
<?php layoutFooter(); ?>
