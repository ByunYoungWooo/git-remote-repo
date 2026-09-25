-- 시드 데이터
INSERT INTO employees (employee_id, login_username, password_hash, name, department, position, role, leave_quota) VALUES
  ('8526301346', 'admin', '$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', '관리자', '경영지원팀', '팀장', 'admin', 20),
  ('0000000001', 'emp01', '$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', '홍길동', '개발팀', '사원', 'employee', 15),
  ('0000000002', 'emp02', '$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', '김철수', '개발팀', '대리', 'employee', 15);

INSERT INTO holidays (year, date, name) VALUES
  (2026, '2026-01-01', '신년'),
  (2026, '2026-02-17', '설날 (설)'),
  (2026, '2026-03-01', '삼일절'),
  (2026, '2026-03-03', '제수 (대체공휴일)'),
  (2026, '2026-04-05', '제헌절'),
  (2026, '2026-05-01', '근로자의 날'),
  (2026, '2026-05-25', '부처님오신날 (대체공휴일)'),
  (2026, '2026-06-06', '현충일'),
  (2026, '2026-08-15', '광복절'),
  (2026, '2026-09-24', '추석 전야 (대체공휴일)'),
  (2026, '2026-09-25', '추석'),
  (2026, '2026-10-03', '개천절'),
  (2026, '2026-10-09', '한글날');
