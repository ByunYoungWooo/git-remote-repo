<?php
/**
 * Model: Leave
 */
require_once __DIR__ . '/../../config.php';

final class Leave
{
    public static function all(): array
    {
        $stmt = getDB()->query(
            'SELECT l.*, e.name AS employee_name
             FROM leaves l
             JOIN employees e ON e.employee_id = l.employee_id
             ORDER BY l.start_date DESC'
        );
        return $stmt->fetchAll();
    }

    public static function pending(): array
    {
        $stmt = getDB()->query(
            "SELECT l.*, e.name AS employee_name
             FROM leaves l JOIN employees e ON e.employee_id = l.employee_id
             WHERE l.status = 'pending'
             ORDER BY l.start_date DESC"
        );
        return $stmt->fetchAll();
    }

    public static function apply(array $d): int
    {
        $stmt = getDB()->prepare(
            'INSERT INTO leaves (employee_id, leave_type, start_date, end_date, duration_days)
             VALUES (?,?,?,?,?)'
        );
        $stmt->execute([
            $d['employee_id'], $d['leave_type'], $d['start_date'], $d['end_date'],
            $d['duration_days'],
        ]);
        return (int) getDB()->lastInsertId();
    }

    public static function approve(int $id, string $approvedBy): void
    {
        $stmt = getDB()->prepare("UPDATE leaves SET status='approved', approved_by=?, approved_at=NOW() WHERE id=?");
        $stmt->execute([$approvedBy, $id]);
    }

    public static function reject(int $id, string $approvedBy): void
    {
        $stmt = getDB()->prepare("UPDATE leaves SET status='rejected', approved_by=?, approved_at=NOW() WHERE id=?");
        $stmt->execute([$approvedBy, $id]);
    }

    public static function daysUsedThisYear(int $employeeId): int
    {
        $stmt = getDB()->prepare(
            "SELECT COALESCE(SUM(duration_days),0) FROM leaves
             WHERE employee_id = ? AND status = 'approved' AND YEAR(start_date) = YEAR(CURDATE())"
        );
        $stmt->execute([$employeeId]);
        return (int) $stmt->fetchColumn();
    }
}
