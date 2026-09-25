<?php
/**
 * Model: Holiday
 */
require_once __DIR__ . '/../../config.php';

final class Holiday
{
    public static function forYear(int $year): array
    {
        $stmt = getDB()->prepare('SELECT * FROM holidays WHERE year = ? ORDER BY date');
        $stmt->execute([$year]);
        return $stmt->fetchAll();
    }

    public static function forRange(string $start, string $end): array
    {
        $stmt = getDB()->prepare('SELECT * FROM holidays WHERE date BETWEEN ? AND ? ORDER BY date');
        $stmt->execute([$start, $end]);
        return $stmt->fetchAll();
    }

    public static function isHoliday(string $date): ?array
    {
        $stmt = getDB()->prepare('SELECT * FROM holidays WHERE date = ? LIMIT 1');
        $stmt->execute([$date]);
        return $stmt->fetch() ?: null;
    }

    public static function create(string $name, string $date, string $type, bool $isWeekend = false): int
    {
        $year = (int) substr($date, 0, 4);
        $stmt = getDB()->prepare('INSERT INTO holidays (holiday_name, date, year, type, is_weekend) VALUES (?,?,?,?,?)');
        $stmt->execute([$name, $date, $year, $type, $isWeekend ? 1 : 0]);
        return (int) getDB()->lastInsertId();
    }

    public static function delete(int $id): void
    {
        $stmt = getDB()->prepare('DELETE FROM holidays WHERE id = ?');
        $stmt->execute([$id]);
    }

    /**
     * 2026년 대한민국 공휴일 (정기 공휴일 기준)
     * 설날 2/16(월)~2/18(수), 추석 9/24(목)~9/28(월)
     */
    public static function seedKorea2026(): int
    {
        $korea2026 = [
            '2026-01-01' => '신정',
            '2026-02-16' => '설날 (설)',
            '2026-03-01' => '삼일절',
            '2026-04-05' => '제헌절',
            '2026-05-01' => '근로자의 날',
            '2026-05-05' => '어린이날',
            '2026-05-25' => '부처님오신날',
            '2026-06-06' => '현충일',
            '2026-08-15' => '광복절',
            '2026-09-24' => '추석 (추석 당일)',
            '2026-10-03' => '국군의 날',
            '2026-10-09' => '한가위 (추석)',
            '2026-10-05' => '개천절',
            '2026-12-25' => '크리스마스',
        ];
        $count = 0;
        foreach ($korea2026 as $date => $name) {
            if (self::isHoliday($date)) continue;
            $year = (int) substr($date, 0, 4);
            $stmt = getDB()->prepare('INSERT INTO holidays (holiday_name, date, year, type, is_weekend) VALUES (?,?,?,?,0)');
            $stmt->execute([$name, $date, $year, 'public_holiday']);
            $count++;
        }
        return $count;
    }
}
