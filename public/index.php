<?php
require_once __DIR__.'/../src/auth.php';
?>
<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>출근부 로그인</title></head>
<body>
<h2>Login</h2>
<form method="post" action="login.php">
    <label>Username: <input type="text" name="username" required></label><br>
    <label>Password: <input type="password" name="password" required></label><br>
    <button type="submit">Login</button>
</form>
<?php if(isset($_GET['error'])) echo '<p style="color:red">'.htmlspecialchars($_GET['error']).'</p>'; ?>
</body></html>