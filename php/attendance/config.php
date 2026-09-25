<?php
/**
 * config.php — 환경 변수 로드 및 DB 연결
 * .env 파일에서 DB_HOST, DB_NAME, DB_USER, DB_PASS 를 읽어 PDO 인스턴스를 반환한다.
 */

require_once __DIR__ . '/src/EnvLoader.php';

EnvLoader::load(__DIR__ . '/.env');

function getDB(): PDO {
    static $pdo = null;
    if ($pdo === null) {
        $host = getenv('DB_HOST') ?: 'localhost';
        $name = getenv('DB_NAME') ?: 'attendance_db';
        $user = getenv('DB_USER') ?: 'root';
        $pass = getenv('DB_PASS') ?: '';
        $dsn  = "mysql:host={$host};dbname={$name};charset=utf8mb4";
        $pdo = new PDO($dsn, $user, $pass, [
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES   => false,
        ]);
    }
    return $pdo;
}

function getAppUrl(string $path = ''): string {
    $base = rtrim(getenv('APP_URL') ?: '', '/');
    return $base . '/' . ltrim($path, '/');
}
