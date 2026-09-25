<?php
/**
 * Auth — 세션 기반 인증 헬퍼
 * - session_start() (안전 호출)
 * - login / logout / requireLogin / requireRole
 * - 세션 30분 비활성 시 자동 로그아웃
 */
require_once __DIR__ . '/../config.php';

function ensureSession(): void
{
    if (session_status() === PHP_SESSION_NONE) {
        session_set_cookie_params([
            'httponly' => true,
            'samesite' => 'Lax',
        ]);
        session_start();
    }
    // 30분 비활성 자동 로그아웃
    $timeout = 1800;
    if (isset($_SESSION['last_active']) && (time() - $_SESSION['last_active']) > $timeout) {
        session_destroy();
        session_start();
        $_SESSION = [];
        return;
    }
    $_SESSION['last_active'] = time();
}

function isLoggedIn(): bool
{
    ensureSession();
    return isset($_SESSION['user_id']);
}

function currentUserName(): ?string
{
    ensureSession();
    return $_SESSION['user_name'] ?? null;
}

function currentUserRole(): ?string
{
    ensureSession();
    return $_SESSION['role'] ?? null;
}

/**
 * 로그인 성공 처리
 */
function doLogin(string $userId, string $userName, string $role): void
{
    ensureSession();
    session_regenerate_id(true);
    $_SESSION['user_id']   = $userId;
    $_SESSION['user_name'] = $userName;
    $_SESSION['role']      = $role;
}

function doLogout(): void
{
    ensureSession();
    $_SESSION = [];
    if (ini_get('session.use_cookies')) {
        $p = session_get_cookie_params();
        setcookie(session_name(), '', time() - 42000, $p['path'], $p['domain'], $p['secure'], $p['httponly']);
    }
    session_destroy();
}

/**
 * 로그인 요구. 미로그인 시 /index.php 로 리다이렉트
 */
function requireLogin(): void
{
    if (!isLoggedIn()) {
        header('Location: ' . getAppUrl('index.php?redirect=' . urlencode($_SERVER['REQUEST_URI'] ?? '')));
        exit;
    }
}

/**
 * 역할 요구. 미충족 시 403
 */
function requireRole(string ...$roles): void
{
    requireLogin();
    $role = currentUserRole();
    if (!in_array($role, $roles, true)) {
        http_response_code(403);
        exit('권한이 없습니다. (필요: ' . implode('/', $roles) . ')');
    }
}

/**
 * CSRF 토큰
 */
function csrfToken(): string
{
    ensureSession();
    if (empty($_SESSION['csrf'])) {
        $_SESSION['csrf'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['csrf'];
}

function csrfField(): string
{
    return '<input type="hidden" name="csrf" value="' . csrfToken() . '">';
}

function verifyCsrf(): void
{
    $token = $_POST['csrf'] ?? $_GET['csrf'] ?? '';
    if (!hash_equals(csrfToken(), $token)) {
        http_response_code(403);
        exit('CSRF 검증 실패');
    }
}

/**
 * HTML 출력 이스케이프
 */
function e(?string $s): string
{
    return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8');
}
