<?php
/**
 * admin/leaves.php — 연차 관리 (승인/거부)
 */
require_once __DIR__ . '/../../src/auth.php';
require_once __DIR__ . '/../../src/Layout.php';
require_once __DIR__ . '/../../src/Model/Leave.php';
require_once __DIR__ . '/../../src/Model/Employee.php';

requireRole('admin','manager');

$msg = $err = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    verifyCsrf();
    $action = $_POST['action'] ?? '';
    $id = (int)($_POST['id'] ?? 0);
    $approver = currentUserName();

    if ($id) {
        if ($action === 'approve') {
            Leave::approve($id, $approver);
            $msg = "연차 승인 완료 (승인자: {$approver})";
        } elseif ($action === 'reject') {
            Leave::reject($id, $approver);
            $msg = "연차 거부 완료 (승인자: {$approver})";
        }
    }
}

$leaves = Leave::all();
$statusMap = ['pending'=>'승인대기','approved'=>'승인','rejected'=>'거부'];
$statusClass = ['pending'=>'warning text-dark','approved'=>'success','rejected'=>'danger'];
$typeMap = ['annual'=>'연차','sick'=>'병가','paid_off'=>'유급'];

layoutHeader('연차 관리', 'leaves');
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <h5>연차 관리</h5>
  <div class="d-flex gap-2">
    <span class="badge bg-warning text-dark align-self-center">대기 <?= count(array_filter($leaves, fn($l) => $l['status']==='pending')) ?>건</span>
    <span class="badge bg-success align-self-center">승인 <?= count(array_filter($leaves, fn($l) => $l['status']==='approved')) ?>건</span>
    <span class="badge bg-danger align-self-center">거부 <?= count(array_filter($leaves, fn($l) => $l['status']==='rejected')) ?>건</span>
  </div>
</div>

<?php if ($msg): ?><div class="alert alert-success py-2"><?= e($msg) ?></div><?php endif; ?>

<div class="card shadow-sm">
  <div class="table-responsive">
    <table class="table table-sm table-hover mb-0">
      <thead><tr>
        <th>직원</th><th>부서</th><th>구분</th><th>기간</th><th>일수</th><th>상태</th><th>신청일</th><th>승인자</th><th>승인일</th><th>처리</th>
      </tr></thead>
      <tbody>
        <?php foreach ($leaves as $l):
          $emp = Employee::findByEmployeeId($l['employee_id']);
        ?>
        <tr>
          <td class="fw-bold"><?= e($l['employee_name'] ?? ($emp['name'] ?? '?')) ?></td>
          <td><?= e($emp['department'] ?? '-') ?></td>
          <td><span class="badge bg-<?= $l['leave_type']==='annual'?'primary':($l['leave_type']==='sick'?'danger':'info text-dark') ?>"><?= $typeMap[$l['leave_type']] ?? e($l['leave_type']) ?></span></td>
          <td>
            <?= e($l['start_date']) ?> ~ <?= e($l['end_date']) ?>
            <?php if ($l['start_date'] !== $l['end_date']): ?>
              <small class="text-muted">(<?= (int)$l['duration_days'] ?>일)</small>
            <?php endif; ?>
          </td>
          <td class="fw-bold"><?= (int)$l['duration_days'] ?></td>
          <td><span class="badge bg-<?= $statusClass[$l['status']] ?? 'secondary' ?>"><?= $statusMap[$l['status']] ?? e($l['status']) ?></span></td>
          <td><small><?= e(substr($l['created_at'] ?? '', 0, 10)) ?></small></td>
          <td><?= e($l['approved_by'] ?? '-') ?></td>
          <td><small><?= e(substr($l['approved_at'] ?? '', 0, 16)) ?></small></td>
          <td>
            <?php if ($l['status'] === 'pending'): ?>
              <div class="d-flex gap-1">
                <form method="post">
                  <?= csrfField() ?>
                  <input type="hidden" name="action" value="approve">
                  <input type="hidden" name="id" value="<?= (int)$l['id'] ?>">
                  <button class="btn btn-sm btn-success">승인</button>
                </form>
                <form method="post" onsubmit="return confirm('거부하시겠습니까?')">
                  <?= csrfField() ?>
                  <input type="hidden" name="action" value="reject">
                  <input type="hidden" name="id" value="<?= (int)$l['id'] ?>">
                  <button class="btn btn-sm btn-outline-danger">거부</button>
                </form>
              </div>
            <?php else: ?>
              <span class="text-muted">처리됨</span>
            <?php endif; ?>
          </td>
        </tr>
        <?php endforeach; ?>
        <?php if (empty($leaves)): ?><tr><td colspan="10" class="text-center text-muted py-3">연차 기록이 없습니다</td></tr><?php endif; ?>
      </tbody>
    </table>
  </div>
</div>

<div class="card shadow-sm mt-3">
  <div class="card-header bg-white fw-bold">직원이용 현황 (<?= date('Y') ?>년 연차)</div>
  <div class="table-responsive">
    <table class="table table-sm mb-0">
      <thead><tr><th>이름</th><th>부서</th><th>잔여일수</th><th>사용일수</th></tr></thead>
      <tbody>
        <?php foreach (Employee::all() as $emp):
          if ($emp['role'] !== 'employee') continue;
          $used = Leave::daysUsedThisYear((int)$emp['employee_id']);
          $total = 15;
          $remain = max(0, $total - $used);
        ?>
        <tr>
          <td class="fw-bold"><?= e($emp['name']) ?></td>
          <td><?= e($emp['department']) ?></td>
          <td><span class="badge bg-<?= $remain > 0 ? 'success' : 'danger' ?>"><?= $remain ?>일</span></td>
          <td><?= $used ?>일</td>
        </tr>
        <?php endforeach; ?>
      </tbody>
    </table>
  </div>
</div>
<?php layoutFooter(); ?>
