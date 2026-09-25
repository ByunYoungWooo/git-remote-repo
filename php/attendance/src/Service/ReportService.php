<?php
/**
 * Service: ReportService — CSV/Excel 내보내기
 */
require_once __DIR__ . '/../../config.php';

final class ReportService
{
    /**
     * 월별 출석 내역 CSV
     */
    public static function attendanceCsv(string $yearMonth): string
    {
        $start = $yearMonth . '-01';
        $end   = date('Y-m-t', strtotime($start));
        $rows  = [
            'employee_id,name,department,check_date,time_in,time_out,status,reason'
        ];
        $stmt = getDB()->prepare(
            'SELECT al.employee_id, e.name, e.department, al.check_date, al.time_in, al.time_out, al.status, al.reason
             FROM attendance_logs al
             JOIN employees e ON e.employee_id = al.employee_id
             WHERE al.check_date BETWEEN ? AND ?
             ORDER BY al.check_date, e.name'
        );
        $stmt->execute([$start, $end]);
        foreach ($stmt as $r) {
            $rows[] = implode(',', array_map(
                fn($v) => '"' . str_replace('"', '""', (string)$v) . '"',
                [$r['employee_id'], $r['name'], $r['department'], $r['check_date'], $r['time_in'], $r['time_out'], $r['status'], $r['reason']]
            ));
        }
        return implode("\n", $rows);
    }

    /**
     * 연차 현황 CSV
     */
    public static function leaveCsv(): string
    {
        $rows = ['employee_id,name,leave_type,start_date,end_date,days,status,applied_by,approved_by'];
        $stmt = getDB()->query(
            'SELECT l.employee_id, e.name, l.leave_type, l.start_date, l.end_date, l.duration_days, l.status, l.applied_by, l.approved_by
             FROM leaves l JOIN employees e ON e.employee_id = l.employee_id
             ORDER BY l.start_date DESC'
        );
        foreach ($stmt as $r) {
            $rows[] = implode(',', array_map(
                fn($v) => '"' . str_replace('"', '""', (string)$v) . '"',
                [$r['employee_id'], $r['name'], $r['leave_type'], $r['start_date'], $r['end_date'], $r['duration_days'], $r['status'], $r['applied_by'], $r['approved_by']]
            ));
        }
        return implode("\n", $rows);
    }
}
