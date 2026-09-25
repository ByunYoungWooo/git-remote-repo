-- 출석관리 Pro — DB 스키마 (v2, Model 코드와 정합)
SET NAMES utf8mb4;

DROP TABLE IF EXISTS attendance_logs;
DROP TABLE IF EXISTS leaves;
DROP TABLE IF EXISTS holidays;
DROP TABLE IF EXISTS employees;

-- ============================================
-- employees
-- ============================================
CREATE TABLE employees (
  id                    INT AUTO_INCREMENT PRIMARY KEY,
  employee_id           VARCHAR(20)  NOT NULL UNIQUE,
  login_username        VARCHAR(50)  NOT NULL UNIQUE,
  password_hash         VARCHAR(255) NOT NULL,
  name                  VARCHAR(50)  NOT NULL,
  department            VARCHAR(50)  NOT NULL DEFAULT '',
  position              VARCHAR(50)  NOT NULL DEFAULT '',
  email                 VARCHAR(100) NOT NULL DEFAULT '',
  phone                 VARCHAR(30)  NOT NULL DEFAULT '',
  role                  ENUM('employee','manager','admin') NOT NULL DEFAULT 'employee',
  attendance_time_in    TIME NOT NULL DEFAULT '09:00:00',
  attendance_time_out   TIME NOT NULL DEFAULT '18:00:00',
  leave_quota           INT NOT NULL DEFAULT 15,
  leave_used            INT NOT NULL DEFAULT 0,
  active                TINYINT(1) NOT NULL DEFAULT 1,
  created_at            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- holidays
-- ============================================
CREATE TABLE holidays (
  id      INT AUTO_INCREMENT PRIMARY KEY,
  year    SMALLINT NOT NULL,
  date    DATE NOT NULL,
  name    VARCHAR(100) NOT NULL,
  UNIQUE KEY uq_date (date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- attendance_logs
-- ============================================
CREATE TABLE attendance_logs (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  employee_id VARCHAR(20)  NOT NULL,
  check_date  DATE         NOT NULL,
  time_in     TIME         NULL,
  time_out    TIME         NULL,
  status      ENUM('present','late','early_leave','absent','leave') NOT NULL DEFAULT 'present',
  reason      VARCHAR(255) NULL,
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_emp_date (employee_id, check_date),
  CONSTRAINT fk_att_emp FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- leaves
-- ============================================
CREATE TABLE leaves (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  employee_id   VARCHAR(20)  NOT NULL,
  leave_type    ENUM('annual','sick','unpaid') NOT NULL DEFAULT 'annual',
  start_date    DATE NOT NULL,
  end_date      DATE NOT NULL,
  duration_days DECIMAL(5,1) NOT NULL DEFAULT 1,
  reason        VARCHAR(255) NULL,
  status        ENUM('pending','approved','rejected','cancelled') NOT NULL DEFAULT 'pending',
  approved_by   VARCHAR(20) NULL,
  approved_at   TIMESTAMP NULL,
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_leave_emp FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE,
  CONSTRAINT fk_leave_approver FOREIGN KEY (approved_by) REFERENCES employees(employee_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
