<?php
/**
 * Model: Employee
 */
require_once __DIR__ . '/../../config.php';

final class Employee
{
    public static function all(): array
    {
        $stmt = getDB()->query('SELECT * FROM employees ORDER BY name');
        return $stmt->fetchAll();
    }

    public static function findByEmployeeId(string $employeeId): ?array
    {
        $stmt = getDB()->prepare('SELECT * FROM employees WHERE employee_id = ?');
        $stmt->execute([$employeeId]);
        return $stmt->fetch() ?: null;
    }

    public static function findByLogin(string $username): ?array
    {
        $stmt = getDB()->prepare('SELECT * FROM employees WHERE login_username = ? LIMIT 1');
        $stmt->execute([$username]);
        return $stmt->fetch() ?: null;
    }

    public static function create(array $d): int
    {
        $cols = ['employee_id','name','department','position','email','phone','login_username','password_hash','role','attendance_time_in','attendance_time_out'];
        $vals = [];
        foreach ($cols as $c) {
            $vals[] = $d[$c] ?? null;
        }
        $sql = 'INSERT INTO employees (' . implode(',', $cols) . ') VALUES (' . rtrim(str_repeat('?,', count($cols)), ',') . ')';
        $stmt = getDB()->prepare($sql);
        $stmt->execute($vals);
        return (int) getDB()->lastInsertId();
    }

    public static function update(int $id, array $d): void
    {
        $allowed = ['employee_id','name','department','position','email','phone','login_username','password_hash','role','attendance_time_in','attendance_time_out'];
        $sets = [];
        $vals = [];
        foreach ($allowed as $c) {
            if (array_key_exists($c, $d)) {
                $sets[] = "{$c} = ?";
                $vals[] = $d[$c];
            }
        }
        if (!$sets) return;
        $vals[] = $id;
        $stmt = getDB()->prepare('UPDATE employees SET ' . implode(',', $sets) . ' WHERE id = ?');
        $stmt->execute($vals);
    }

    public static function delete(int $id): void
    {
        $stmt = getDB()->prepare('DELETE FROM employees WHERE id = ?');
        $stmt->execute([$id]);
    }

    /**
     * 현재 월 잔여 연차 계산: 총 15일 - 승인된 annual 연차 사용일수
     */
    public static function remainingAnnual(int $employeeId): int
    {
        $stmt = getDB()->prepare(
            "SELECT COALESCE(SUM(duration_days),0) FROM leaves
             WHERE employee_id = ? AND leave_type = 'annual' AND status = 'approved'
             AND YEAR(start_date) = YEAR(CURDATE())"
        );
        $stmt->execute([$employeeId]);
        $used = (int) $stmt->fetchColumn();
        return max(0, 15 - $used);
    }
}
