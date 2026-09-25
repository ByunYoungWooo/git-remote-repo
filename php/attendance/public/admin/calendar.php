<?php
/**
 * admin/calendar.php — 캘린더/공휴일 관리
 */
require_once __DIR__ . '/../../src/auth.php';
require_once __DIR__ . '/../../src/Layout.php';
require_once __DIR__ . '/../../src/Model/Holiday.php';

requireRole('admin');

$msg = $err = '';
$year = (int)($_GET['year'] ?? date('Y'));

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    verifyCsrf();
    $action = $_POST['action'] ?? '';
    if ($action === 'add') {
        $name = trim($_POST['holiday_name'] ?? '');
        $date = $_POST['date'] ?? '';
        $type = $_POST['type'] ?? 'public';
        if ($name && $date) {
            Holiday::create($name, $date, $type);
            $msg = "공휴일 추가: {$name} ({$date})";
        } else {
            $err = '공휴일 이름과 날짜는 필수입니다.';
        }
    } elseif ($action === 'delete') {
        $id = (int)($_POST['id'] ?? 0);
        if ($id) {
            Holiday::delete($id);
            $msg = '삭제되었습니다.';
        }
    }
}

$holidays = Holiday::forYear($year);
$holidayDates = array_column($holidays, 'date');
$prevYear = $year - 1;
$nextYear = $year + 1;

layoutHeader('캘린더 관리', 'calendar');
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <h5>공휴일 관리</h5>
  <div class="btn-group">
    <a href="?year=<?= $prevYear ?>" class="btn btn-sm btn-outline-secondary">&lt; <?= $prevYear ?></a>
    <span class="btn btn-sm btn-primary"><?= $year ?>년</span>
    <a href="?year=<?= $nextYear ?>" class="btn btn-sm btn-outline-secondary"><?= $nextYear ?> &gt;</a>
  </div>
</div>

<?php if ($msg): ?><div class="alert alert-success py-2"><?= e($msg) ?></div><?php endif; ?>
<?php if ($err): ?><div class="alert alert-danger py-2"><?= e($err) ?></div><?php endif; ?>

<div class="row g-4">
  <div class="col-md-7">
    <div class="card shadow-sm">
      <div class="card-header bg-white fw-bold"><?= $year ?>년 공휴일 (<?= count($holidays) ?>개)</div>
      <div class="table-responsive">
        <table class="table table-sm table-hover mb-0">
          <thead><tr><th>날짜</th><th>요일</th><th>공휴일</th><th>구분</th><th></th></tr></thead>
          <tbody>
            <?php
            $dow = ['월','화','수','목','금','토','일'];
            foreach ($holidays as $h):
              $day = (int)date('w', strtotime($h['date']));
              $dowName = $dow[$day === 0 ? 6 : $day - 1];
            ?>
            <tr>
              <td class="fw-bold"><?= e($h['date']) ?></td>
              <td><span class="badge bg-<?= $day===0||$day===6 ? 'danger' : 'secondary' ?>"><?= $dowName ?></span></td>
              <td><?= e($h['holiday_name']) ?></td>
              <td><span class="badge bg-<?= $h['type']==='public' ? 'primary' : ($h['type']==='observed' ? 'info text-dark' : 'warning text-dark') ?>"><?= e($h['type']) ?></span></td>
              <td>
                <form method="post" class="d-inline" onsubmit="return confirm('삭제하시겠습니까?')">
                  <?= csrfField() ?>
                  <input type="hidden" name="action" value="delete">
                  <input type="hidden" name="id" value="<?= (int)$h['id'] ?>">
                  <button class="btn btn-sm btn-outline-danger">삭제</button>
                </form>
              </td>
            </tr>
            <?php endforeach; ?>
            <?php if (empty($holidays)): ?><tr><td colspan="5" class="text-center text-muted py-3">등록된 공휴일이 없습니다</td></tr><?php endif; ?>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <div class="col-md-5">
    <div class="card shadow-sm mb-3">
      <div class="card-header bg-white fw-bold">공휴일 추가</div>
      <div class="card-body">
        <form method="post">
          <?= csrfField() ?>
          <input type="hidden" name="action" value="add">
          <div class="mb-2">
            <label class="form-label">공휴일 이름</label>
            <input type="text" name="holiday_name" class="form-control" placeholder="예: 대체공휴일" required>
          </div>
          <div class="mb-2">
            <label class="form-label">날짜</label>
            <input type="date" name="date" class="form-control" required>
          </div>
          <div class="mb-3">
            <label class="form-label">구분</label>
            <select name="type" class="form-select">
              <option value="public">공공 공휴일</option>
              <option value="observed">대체 휴일</option>
              <option value="special">특별 공휴일</option>
            </select>
          </div>
          <button class="btn btn-primary w-100">추가</button>
        </form>
      </div>
    </div>

    <div class="card shadow-sm">
      <div class="card-header bg-white fw-bold">연도별 요약</div>
      <div class="card-body">
        <?php
        $byType = [];
        foreach ($holidays as $h) {
            $t = $h['type'] ?? 'other';
            $byType[$t] = ($byType[$t] ?? 0) + 1;
        }
        $labels = ['public'=>'공공 공휴일','observed'=>'대체 휴일','special'=>'특별 공휴일'];
        $colors = ['public'=>'bg-primary','observed'=>'bg-info text-dark','special'=>'bg-warning text-dark'];
        ?>
        <?php foreach ($byType as $t => $cnt): ?>
          <div class="d-flex justify-content-between py-1">
            <span><span class="badge <?= $colors[$t] ?? 'bg-secondary' ?>"><?= $labels[$t] ?? e($t) ?></span></span>
            <span class="fw-bold"><?= $cnt ?>일</span>
          </div>
        <?php endforeach; ?>
        <hr>
        <div class="d-flex justify-content-between fw-bold">
          <span>합계</span><span><?= count($holidays) ?>일</span>
        </div>
      </div>
    </div>
  </div>
</div>
<?php layoutFooter(); ?>
