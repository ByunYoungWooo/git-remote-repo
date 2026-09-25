<?php
require_once __DIR__ . '/../src/auth.php';
doLogout();
header('Location: index.php');
exit;
