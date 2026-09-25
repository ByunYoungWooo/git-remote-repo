<?php
/**
 * Model: AttendanceLog
 */
require_once __DIR__ . '/../../config.php';

final class AttendanceLog
{
    public static function forDate(string $date): array
    {
        $stmt = getDB()->prepare(
            'SELECT al.*, e.name, e.department, e.attendance_time_in AS expected_in, e.attendance_time_out AS expected_out
             FROM attendance_logs al
             JOIN employees e ON e.employee_id = al.employee_id
             WHERE al.check_date = ? ORDER BY e.name'
        );
        $stmt->execute([$date]);
        return $stmt->fetchAll();
    }

    /**
     * 오늘 출퇴근 체크
     * - 출근: time_in 없으면 설정, status 계산 (late)
     * - 퇴근: time_out 없으면 설정 (early_leave 감지)
     */
    public static function check(string $employeeId, string $date, bool $isClockIn, ?string $reason = null): array
    {
        $pdo = getDB();
        $stmt = $pdo->prepare('SELECT * FROM attendance_logs WHERE employee_id = ? AND check_date = ?');
        $stmt->execute([$employeeId, $date]);
        $row = $stmt->fetch();

        $emp = Employee::findByEmployeeId($employeeId);
        if (!$emp) {
            return ['error' => '존재하지 않는 직원입니다.'];
        }

        $now = date('H:i:s');
        $expectedIn  = $emp['attendance_time_in'] ?? '09:00:00';
        $expectedOut = $emp['attendance_time_out'] ?? '18:00:00';

        if (!$row) {
            // 새로 생성
            if ($isClockIn) {
                $status = ($now > $expectedIn) ? 'late' : 'present';
                $stmt = $pdo->prepare(
                    'INSERT INTO attendance_logs (employee_id, check_date, time_in, status, reason, auto_checked)
                     VALUES (?,?,?,?,?,1)'
                );
                $stmt->execute([$employeeId, $date, $now, $status, $reason]);
                return ['ok' => true, 'message' => "출근 기록 완료: {$now}", 'status' => $status];
            }
        }

        if ($isClockIn) {
            if ($row['time_in']) {
                return ['error' => '이미 출근 기록이 있습니다.'];
            }
            $status = ($now > $expectedIn) ? 'late' : 'present';
            $upd = $pdo->prepare('UPDATE attendance_logs SET time_in = ?, status = ?, reason = ? WHERE id = ?');
            $upd->execute([$now, $status, $reason, $row['id']]);
            return ['ok' => true, 'message' => "출근 기록 완료: {$now}", 'status' => $status];
        } else {
            if (!$row['time_in']) {
                return ['error' => '출근 기록이 없습니다. 먼저 출근 체크하세요.'];
            }
            if ($row['time_out']) {
                return ['error' => '이미 퇴근 기록이 있습니다.'];
            }
            $status = ($now < $expectedOut) ? 'early_leave' : 'present';
            $upd = $pdo->prepare('UPDATE attendance_logs SET time_out = ?, status = ? WHERE id = ?');
            $upd->execute([$now, $status, $row['id']]);
            return ['ok' => true, 'message' => "퇴근 기록 완료: {$now}", 'status' => $status];
        }
    }

    /**
     * 월별 정산 데이터
     */
    public static function monthly(string $employeeId, string $yearMonth): array
    {
        $stmt = getDB()->prepare(
            'SELECT * FROM attendance_logs
             WHERE employee_id = ? AND check_date BETWEEN ? AND ?
             ORDER BY check_date'
        );
        $start = $yearMonth . '-01';
        $end   = date('Y-m-t', strtotime($start));
        $stmt->execute([$employeeId, $start, $end]);
        return $stmt->fetchAll();
    }

    public static function stats(string $yearMonth): array
    {
        $start = $yearMonth . '-01';
        $end   = date('Y-m-t', strtotime($start));
        $stmt = getDB()->prepare(
            'SELECT
                COUNT(*) AS total,
                SUM(status = "present") AS present_count,
                SUM(status = "late") AS late_count,
                SUM(status = "absent") AS absent_count,
                SUM(status = "early_leave") AS early_count
             FROM attendance_logs
             WHERE check_date BETWEEN ? AND ?'
        );
        $stmt->execute([$start, $end]);
        return $stmt->fetch();
    }

    public static function statsByEmployee(string $yearMonth): array
    {
        $start = $yearMonth . '-01';
        $end   = date('Y-m-t', strtotime($start));
        $stmt = getDB()->prepare(
            'SELECT e.name, e.department,
                COUNT(al.id) AS days,
                SUM(al.status = "late") AS late,
                SUM(al.status = "absent") AS absent,
                SUM(al.status = "early_leave") AS early
             FROM employees e
             LEFT JOIN attendance_logs al ON al.employee_id = e.employee_id AND al.check_date BETWEEN ? AND ?
             GROUP BY e.id
             ORDER BY e.name'
        );
        $stmt->execute([$start, $end]);
        return $stmt->fetchAll();
    }
}
