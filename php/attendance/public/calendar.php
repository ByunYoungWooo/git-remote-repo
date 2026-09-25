<?php
require_once __DIR__ . '/../src/auth.php';
require_once __DIR__ . '/../src/Layout.php';
require_once __DIR__ . '/../src/Model/Holiday.php';

requireLogin();

$year  = (int)($_GET['year'] ?? date('Y'));
$month = (int)($_GET['month'] ?? date('n'));
$first = mktime(0, 0, 0, $month, 1, $year);
$daysInMonth = (int)date('t', $first);
$startWeekday = (int)date('w', $first); // 0=Sunday

$holidays = Holiday::forRange(date('Y-m-01', $first), date('Y-m-t', $first));
$holidayMap = [];
foreach ($holidays as $h) {
    $holidayMap[$h['date']] = $h;
}

// 승인된 연차 (현재 달)
$monthStart = date('Y-m-01', $first);
$monthEnd   = date('Y-m-t', $first);
$stmt = getDB()->prepare(
    'SELECT l.employee_id, e.name, l.start_date, l.end_date, l.leave_type
     FROM leaves l JOIN employees e ON e.employee_id = l.employee_id
     WHERE l.status = "approved" AND l.start_date <= ? AND l.end_date >= ?'
);
$stmt->execute([$monthEnd, $monthStart]);
$leaves = $stmt->fetchAll();
$leaveMap = [];
foreach ($leaves as $lv) {
    // 각 날짜별
    $d = new DateTime($lv['start_date']);
    $end = new DateTime($lv['end_date']);
    while ($d <= $end) {
        $key = $d->format('Y-m-d');
        $leaveMap[$key][] = $lv;
        $d->modify('+1 day');
    }
}

layoutHeader('캘린더', 'calendar');
?>
<div class="card shadow-sm mb-3">
  <div class="card-body d-flex justify-content-between align-items-center">
    <div class="btn-group">
      <a class="btn btn-outline-secondary" href="?year=<?= $year - 1 ?>&month=<?= $month ?>"><i class="bi bi-chevron-left"></i></a>
      <a class="btn btn-outline-secondary" href="?year=<?= $year + 1 ?>&month=<?= $month ?>"><i class="bi bi-chevron-right"></i></a>
    </div>
    <h4 class="mb-0"><?= $year ?>년 <?= $month ?>월</h4>
    <div class="btn-group">
      <a class="btn btn-outline-secondary btn-sm" href="?year=<?= $year ?>&month=<?= $month - 1 ?>"><i class="bi bi-chevron-left"></i></a>
      <a class="btn btn-outline-secondary btn-sm" href="?year=<?= $year ?>&month=<?= $month + 1 ?>"><i class="bi bi-chevron-right"></i></a>
    </div>
  </div>
</div>

<div class="card shadow-sm">
  <div class="table-responsive">
  <table class="table table-bordered mb-0 text-center">
    <thead class="table-light">
      <tr>
        <?php foreach (['일','월','화','수','목','금','토'] as $d): ?>
        <th class="py-2 fw-bold <?= $d==='일'?'text-danger':($d==='토'?'text-primary':'') ?>"><?= $d ?></th>
        <?php endforeach; ?>
      </tr>
    </thead>
    <tbody>
      <?php
      $cellCount = ceil(($startWeekday + $daysInMonth) / 7) * 7;
      for ($i = 0; $i < $cellCount; $i++):
        $day = $i - $startWeekday + 1;
        if ($day < 1 || $day > $daysInMonth) {
            echo '<td class="bg-light py-2"></td>';
            if (($i+1) % 7 === 0) echo '</tr>';
            continue;
        }
        $dateStr = date('Y-m-01', mktime(0,0,0,$month,$day,$year)) . '-' . str_pad($day, 2, '0', STR_PAD_LEFT);
        $dateStr = sprintf('%04d-%02d-%02d', $year, $month, $day);
        $weekday = date('w', mktime(0,0,0,$month,$day,$year));
        $isHoli = isset($holidayMap[$dateStr]);
        $isLeave = isset($leaveMap[$dateStr]);
        $cls = '';
        $badge = '';
        if ($isHoli) {
            $cls = 'bg-danger bg-opacity-10';
            $badge = '<div class="badge bg-danger mt-1">' . e($holidayMap[$dateStr]['holiday_name']) . '</div>';
        }
        if ($isLeave) {
            $cls = 'bg-info bg-opacity-10';
            $names = array_unique(array_map(fn($l) => $l['name'], $leaveMap[$dateStr]));
            $badge .= '<div class="badge bg-info text-dark mt-1">' . e(implode(', ', $names)) . ' 연차</div>';
        }
        $wdCls = $weekday === 0 ? 'text-danger' : ($weekday === 6 ? 'text-primary' : '');
        ?>
        <td class="py-2 align-middle <?= $cls ?>">
          <div class="fw-bold <?= $wdCls ?>"><?= $day ?></div>
          <?= $badge ?>
        </td>
        <?php
        if (($i+1) % 7 === 0) echo '</tr>';
      endfor;
      ?>
    </tbody>
  </table>
  </div>
</div>
<?php layoutFooter(); ?>
