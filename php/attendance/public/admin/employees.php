<?php
/**
 * admin/employees.php — 직원 관리
 */
require_once __DIR__ . '/../../src/auth.php';
require_once __DIR__ . '/../../src/Layout.php';
require_once __DIR__ . '/../../src/Model/Employee.php';

requireRole('admin');

$msg = $err = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    verifyCsrf();
    $action = $_POST['action'] ?? '';

    if ($action === 'create') {
        $d = [
            'employee_id'      => trim($_POST['employee_id'] ?? ''),
            'name'             => trim($_POST['name'] ?? ''),
            'department'       => trim($_POST['department'] ?? ''),
            'position'         => trim($_POST['position'] ?? ''),
            'email'            => trim($_POST['email'] ?? ''),
            'phone'            => trim($_POST['phone'] ?? ''),
            'login_username'   => trim($_POST['login_username'] ?? ''),
            'password_hash'    => password_hash($_POST['password'] ?? '', PASSWORD_DEFAULT),
            'role'             => $_POST['role'] ?? 'employee',
            'attendance_time_in'  => ($_POST['time_in'] ?? '09:00') . ':00',
            'attendance_time_out' => ($_POST['time_out'] ?? '18:00') . ':00',
        ];
        if ($d['employee_id'] && $d['name'] && $d['login_username'] && $d['password_hash'] !== password_hash('', PASSWORD_DEFAULT)) {
            Employee::create($d);
            $msg = '직원이 추가되었습니다.';
        } else {
            $err = 'employee_id, 이름, 로그인 ID, 비밀번호는 필수입니다.';
        }
    } elseif ($action === 'delete') {
        $id = (int)($_POST['id'] ?? 0);
        if ($id) {
            try {
                Employee::delete($id);
                $msg = '삭제되었습니다.';
            } catch (PDOException $e) {
                $err = '삭제 실패: 출석/연차 기록이 있는 직원은 삭제할 수 없습니다.';
            }
        }
    } elseif ($action === 'update') {
        $id = (int)($_POST['id'] ?? 0);
        $d = [];
        foreach (['employee_id','name','department','position','email','phone','login_username','role'] as $f) {
            if (array_key_exists($f, $_POST)) $d[$f] = trim($_POST[$f]);
        }
        if (!empty($_POST['time_in']))  $d['attendance_time_in']  = $_POST['time_in'] . ':00';
        if (!empty($_POST['time_out'])) $d['attendance_time_out'] = $_POST['time_out'] . ':00';
        if (!empty($_POST['password'])) $d['password_hash'] = password_hash($_POST['password'], PASSWORD_DEFAULT);
        Employee::update($id, $d);
        $msg = '수정되었습니다.';
    }
}

$employees = Employee::all();
layoutHeader('직원 관리', 'admin');
?>
<div class="d-flex justify-content-between align-items-center mb-4">
  <h4 class="mb-0"><i class="bi bi-people me-2"></i>직원 관리</h4>
  <button class="btn btn-primary" data-bs-toggle="collapse" data-bs-target="#addForm">+ 직원 추가</button>
</div>

<?php if ($msg): ?><div class="alert alert-success py-2"><?= e($msg) ?></div><?php endif; ?>
<?php if ($err): ?><div class="alert alert-danger py-2"><?= e($err) ?></div><?php endif; ?>

<div class="collapse mb-4" id="addForm">
  <div class="card border-primary">
    <div class="card-body">
      <form method="post" action="">
        <?= csrfField() ?>
        <input type="hidden" name="action" value="create">
        <div class="row g-3">
          <div class="col-md-3"><label class="form-label">직번 (employee_id)</label><input name="employee_id" class="form-control" required></div>
          <div class="col-md-3"><label class="form-label">이름</label><input name="name" class="form-control" required></div>
          <div class="col-md-3"><label class="form-label">부서</label><input name="department" class="form-control"></div>
          <div class="col-md-3"><label class="form-label">직급</label><input name="position" class="form-control"></div>
          <div class="col-md-3"><label class="form-label">이메일</label><input name="email" type="email" class="form-control"></div>
          <div class="col-md-3"><label class="form-label">전화</label><input name="phone" class="form-control"></div>
          <div class="col-md-3"><label class="form-label">로그인 ID</label><input name="login_username" class="form-control" required></div>
          <div class="col-md-3"><label class="form-label">비밀번호</label><input name="password" type="password" class="form-control" required></div>
          <div class="col-md-3"><label class="form-label">역할</label>
            <select name="role" class="form-select">
              <option value="employee">직원</option>
              <option value="manager">팀장</option>
              <option value="admin">관리자</option>
            </select>
          </div>
          <div class="col-md-3"><label class="form-label">기준 출근</label><input name="time_in" type="time" class="form-control" value="09:00"></div>
          <div class="col-md-3"><label class="form-label">기준 퇴근</label><input name="time_out" type="time" class="form-control" value="18:00"></div>
        </div>
        <button class="btn btn-success mt-3">추가</button>
      </form>
    </div>
  </div>
</div>

<div class="card shadow-sm">
  <div class="table-responsive">
    <table class="table table-hover mb-0">
      <thead class="table-light">
        <tr><th>직번</th><th>이름</th><th>부서</th><th>역할</th><th>기준시간</th><th>연차잔여</th><th></th></tr>
      </thead>
      <tbody>
        <?php foreach ($employees as $emp): ?>
        <tr>
          <td class="font-monospace"><?= e($emp['employee_id']) ?></td>
          <td>
            <?= e($emp['name']) ?>
            <div class="small text-muted"><?= e($emp['email'] ?? '') ?></div>
          </td>
          <td><?= e($emp['department'] ?? '-') ?></td>
          <td>
            <span class="badge bg-<?= $emp['role']==='admin'?'dark':($emp['role']==='manager'?'warning text-dark':'secondary') ?>">
              <?= e($emp['role']) ?>
            </span>
          </td>
          <td class="small">
            <?= e(substr($emp['attendance_time_in'] ?? '09:00',0,5)) ?> ~ <?= e(substr($emp['attendance_time_out'] ?? '18:00',0,5)) ?>
          </td>
          <td><?= Employee::remainingAnnual($emp['id']) ?>일</td>
          <td class="text-end">
            <form method="post" class="d-inline" onsubmit="return confirm('정말 삭제할까요?')">
              <?= csrfField() ?>
              <input type="hidden" name="action" value="delete">
              <input type="hidden" name="id" value="<?= (int)$emp['id'] ?>">
              <button class="btn btn-outline-danger btn-sm"><i class="bi bi-trash"></i></button>
            </form>
          </td>
        </tr>
        <?php endforeach; ?>
      </tbody>
    </table>
  </div>
</div>

<div class="mt-4">
  <a class="btn btn-outline-primary" href="dashboard.php"><i class="bi bi-arrow-left me-1"></i>대시보드로</a>
  <a class="btn btn-outline-secondary ms-1" href="attendance.php">출석 검토</a>
</div>
<?php layoutFooter(); ?>
