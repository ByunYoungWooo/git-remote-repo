<?php
require_once __DIR__ . '/../src/auth.php';
require_once __DIR__ . '/../src/Layout.php';
require_once __DIR__ . '/../src/Model/Leave.php';
require_once __DIR__ . '/../src/Model/Employee.php';

requireLogin();

$msg = $err = '';
$myId = $_SESSION['user_id'];
$emp = Employee::findByEmployeeId($myId);

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    verifyCsrf();
    $action = $_POST['action'] ?? '';
    if ($action === 'apply') {
        $start = $_POST['start_date'] ?? '';
        $end   = $_POST['end_date'] ?? ($start ?: '');
        $type  = $_POST['leave_type'] ?? 'annual';
        if ($start && $end) {
            $days = (int) floor((strtotime($end) - strtotime($start)) / 86400) + 1;
            Leave::apply([
                'employee_id'   => $myId,
                'leave_type'    => $type,
                'start_date'    => $start,
                'end_date'      => $end,
                'duration_days' => $days,
            ]);
            $msg = '연차 신청이 접수되었습니다. 팀장 승인을 기다려 주세요.';
        } else {
            $err = '날짜를 선택해 주세요.';
        }
    }
}

$stmt = getDB()->prepare(
    'SELECT * FROM leaves WHERE employee_id = ? ORDER BY start_date DESC'
);
$stmt->execute([$myId]);
$myLeaves = $stmt->fetchAll();
$remaining = Employee::remainingAnnual($myId);

layoutHeader('연차 관리', 'leaves');
?>
<div class="row g-4">
  <div class="col-md-7">
    <div class="card shadow-sm mb-3">
      <div class="card-body">
        <h5 class="mb-3">연차 신청</h5>
        <?php if ($msg): ?><div class="alert alert-success py-2"><?= e($msg) ?></div><?php endif; ?>
        <?php if ($err): ?><div class="alert alert-danger py-2"><?= e($err) ?></div><?php endif; ?>
        <form method="post" action="">
          <?= csrfField() ?>
          <input type="hidden" name="action" value="apply">
          <div class="row g-3 mb-3">
            <div class="col-md-4">
              <label class="form-label">구분</label>
              <select name="leave_type" class="form-select">
                <option value="annual">연차</option>
                <option value="sick">병가</option>
                <option value="paid_off">유급휴가</option>
              </select>
            </div>
            <div class="col-md-4">
              <label class="form-label">시작일</label>
              <input type="date" name="start_date" class="form-control" required>
            </div>
            <div class="col-md-4">
              <label class="form-label">종료일</label>
              <input type="date" name="end_date" class="form-control" required>
            </div>
          </div>
          <button class="btn btn-primary">신청하기</button>
        </form>
      </div>
    </div>
  </div>
  <div class="col-md-5">
    <div class="card shadow-sm">
      <div class="card-body text-center">
        <h6 class="text-muted">올해 잔여 연차</h6>
        <div class="display-4 fw-bold text-primary"><?= $remaining ?>일</div>
        <small class="text-muted">(총 15일 기준)</small>
      </div>
    </div>
  </div>
</div>

<div class="card shadow-sm mt-4">
  <div class="card-header bg-white fw-bold">내 연차 내역</div>
  <div class="table-responsive">
    <table class="table table-sm mb-0">
      <thead><tr><th>구분</th><th>기간</th><th>일수</th><th>상태</th><th>승인자</th></tr></thead>
      <tbody>
        <?php
        $statusMap = ['pending'=>'승인대기', 'approved'=>'승인', 'rejected'=>'거부'];
        $typeMap = ['annual'=>'연차', 'sick'=>'병가', 'paid_off'=>'유급'];
        foreach ($myLeaves as $r): ?>
          <tr>
            <td><?= $typeMap[$r['leave_type']] ?? $r['leave_type'] ?></td>
            <td><?= e($r['start_date']) ?> ~ <?= e($r['end_date']) ?></td>
            <td><?= (int)$r['duration_days'] ?>일</td>
            <td><span class="badge bg-<?= $r['status']==='approved'?'success':($r['status']==='rejected'?'danger':'warning text-dark') ?>"><?= $statusMap[$r['status']] ?? $r['status'] ?></span></td>
            <td><?= e($r['approved_by'] ?? '-') ?></td>
          </tr>
        <?php endforeach; ?>
        <?php if (!count($myLeaves)): ?><tr><td colspan="5" class="text-center text-muted py-3">기록이 없습니다</td></tr><?php endif; ?>
      </tbody>
    </table>
  </div>
</div>
<?php layoutFooter(); ?>
