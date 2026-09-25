<?php
/**
 * Admin Directory Index
 * Redirect to admin dashboard
 */
require_once __DIR__ . '/../../config.php';
require_once __DIR__ . '/../../src/auth.php';

requireRole('admin');
header('Location: dashboard.php');
exit;
