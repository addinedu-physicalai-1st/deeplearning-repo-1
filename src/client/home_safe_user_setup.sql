-- ============================================================
-- Home Safe - 통합 DB 설정 스크립트
-- 실행: root 로 접속 후 실행
--   mysql -u root -ptrdbpw!1234 < unified_home_safe_setup.sql
--   또는 MySQL 클라이언트에서 source unified_home_safe_setup.sql
--
--
-- DB_USER=root
-- DB_PASSWORD=trdbpw!1234
-- DB_NAME=home_safe_admin
-- 데이터베이스 생성
--   DB_NAME : home_safe_user
--   USER    : homesafeusr
--   PASS    : user1234!
--
-- (아래 스크립트에서 DB/계정을 재생성한 뒤 home_safe_user에 테이블을 생성합니다.)

-- 계정 생성
-- CREATE USER 'homesafeusr'@'localhost' IDENTIFIED BY 'user1234!';

-- 권한 부여 (home_safe_user DB에 대해)
-- GRANT ALL PRIVILEGES ON home_safe_user.* TO 'homesafeusr'@'localhost';


-- CREATE DATABASE IF NOT EXISTS home_safe_user CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- USE home_safe_user;

-- ============================================================

-- 1) 기존 DB 삭제 (있으면 삭제)
SET FOREIGN_KEY_CHECKS = 0;
DROP DATABASE IF EXISTS home_safe_user;
SET FOREIGN_KEY_CHECKS = 1;

-- 2) 계정 삭제 후 재생성
DROP USER IF EXISTS 'homesafeusr'@'localhost';
CREATE USER 'homesafeusr'@'localhost' IDENTIFIED BY 'user1234!';

-- 3) DB 생성 및 권한 부여
CREATE DATABASE home_safe_user CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON home_safe_user.* TO 'homesafeusr'@'localhost';
FLUSH PRIVILEGES;

-- 이후 모든 작업은 home_safe_user 데이터베이스 기준
USE home_safe_user;

-- ============================================================
-- 테이블 생성 (의존 순서: users → event_types → event_logs → auto_report_logs, login_history / system_settings)
-- ============================================================
SET FOREIGN_KEY_CHECKS = 0;

-- 1. 사용자 테이블
CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    rtsp_url VARCHAR(500),
    name VARCHAR(100) NOT NULL,
    gender ENUM('남성', '여성', '기타') NOT NULL,
    blood_type ENUM('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'),
    address VARCHAR(500),
    birth_date DATE,
    emergency_contact VARCHAR(20),
    user_type ENUM('관리자', '일반유저') NOT NULL DEFAULT '일반유저',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    INDEX idx_username (username),
    INDEX idx_user_type (user_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. 이벤트 타입 테이블
CREATE TABLE event_types (
    event_type_id INT AUTO_INCREMENT PRIMARY KEY,
    type_name VARCHAR(50) UNIQUE NOT NULL,
    severity ENUM('정상', '주의', '경고', '위험') NOT NULL DEFAULT '주의',
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    INDEX idx_type_name (type_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. 이벤트 로그 테이블 (add_column 반영: accuracy 포함)
CREATE TABLE event_logs (
    event_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    event_type_id INT NOT NULL,
    event_status ENUM('발생', '조치중', '완료') NOT NULL DEFAULT '발생',
    occurred_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL,
    duration_seconds INT,
    confidence FLOAT,
    hip_height FLOAT,
    spine_angle FLOAT,
    hip_velocity FLOAT,
    video_path VARCHAR(500),
    thumbnail_path VARCHAR(500),
    action_taken ENUM('없음', '1차_메시지발송', '2차_긴급호출') DEFAULT '없음',
    action_result TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    accuracy FLOAT DEFAULT NULL COMMENT '정상 탐지율 (최근 5분 평균, %)',
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (event_type_id) REFERENCES event_types(event_type_id),
    INDEX idx_user_event (user_id, occurred_at),
    INDEX idx_event_type (event_type_id),
    INDEX idx_occurred_at (occurred_at),
    INDEX idx_status (event_status),
    INDEX idx_event_search (user_id, event_type_id, occurred_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. 자동신고 로그 테이블
CREATE TABLE auto_report_logs (
    report_id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    report_target ENUM('119', '112', '비상연락처') NOT NULL,
    report_type ENUM('1차_메시지', '2차_긴급호출') NOT NULL,
    report_content TEXT,
    video_sent BOOLEAN DEFAULT FALSE,
    recipient VARCHAR(100),
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    delivery_status ENUM('대기', '발송중', '성공', '실패') DEFAULT '대기',
    delivery_result TEXT,
    FOREIGN KEY (event_id) REFERENCES event_logs(event_id) ON DELETE CASCADE,
    INDEX idx_event (event_id),
    INDEX idx_target (report_target),
    INDEX idx_sent_at (sent_at),
    INDEX idx_report_search (event_id, report_target, sent_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. 시스템 설정 테이블
CREATE TABLE system_settings (
    setting_id INT AUTO_INCREMENT PRIMARY KEY,
    setting_key VARCHAR(100) UNIQUE NOT NULL,
    setting_value TEXT,
    setting_type ENUM('string', 'int', 'float', 'bool', 'json') DEFAULT 'string',
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_key (setting_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. 로그인 히스토리 테이블
CREATE TABLE login_history (
    login_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    login_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    logout_at TIMESTAMP NULL,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    login_status ENUM('성공', '실패') DEFAULT '성공',
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    INDEX idx_user_login (user_id, login_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- 기본 데이터
-- ============================================================

-- 관리자 계정 (비밀번호: admin123)
INSERT INTO users (username, password_hash, name, gender, user_type) VALUES
('admin', '$2b$12$F3RcrQ18OtiOfuRluzkfr..Aqc5YucQ8W3akL1/3g3YKUhHbBUAOW', '관리자', '남성', '관리자')
ON DUPLICATE KEY UPDATE password_hash=VALUES(password_hash);

-- homesafe 계정 (비밀번호: homesafe1234!)
INSERT INTO users (username, password_hash, name, gender, user_type) VALUES
('homesafe', '$2b$12$clMa7e2aCqK4IegbGYRuCOO1TyNqDdfnxHjVfwR6zBiFw3oiMctoK', '관리자', '남성', '관리자')
ON DUPLICATE KEY UPDATE password_hash=VALUES(password_hash);

-- 이벤트 타입
INSERT INTO event_types (type_name, severity, description) VALUES
('정상', '정상', '정상 상태'),
('낙상', '위험', '넘어지는 행동 감지'),
('쓰러짐', '위험', '바닥에 쓰러진 상태'),
('화재', '위험', '화재 감지'),
('침수', '경고', '침수 감지'),
('외부인침입', '경고', '승인되지 않은 사람 감지'),
('안전영역이탈', '주의', '안전 영역 이탈 감지')
ON DUPLICATE KEY UPDATE event_type_id=event_type_id;

-- 시스템 설정
INSERT INTO system_settings (setting_key, setting_value, setting_type, description) VALUES
('auto_report_enabled', 'true', 'bool', '자동 신고 활성화 여부'),
('first_action_delay', '30', 'int', '1차 조치 대기 시간 (초)'),
('second_action_delay', '180', 'int', '2차 조치 대기 시간 (초)'),
('video_before_seconds', '5', 'int', '이벤트 발생 전 녹화 시간 (초)'),
('video_after_seconds', '10', 'int', '이벤트 발생 후 녹화 시간 (초)'),
('recording_path', '/home/gjkong/dev_ws/yolo/myproj/recordings/', 'string', '녹화 파일 저장 경로'),
('event_video_path', '/home/gjkong/dev_ws/yolo/myproj/events/', 'string', '이벤트 동영상 저장 경로'),
('model_type', '3class', 'string', '사용할 모델 타입 (binary/3class)'),
('confidence_threshold', '0.7', 'float', '낙상 감지 신뢰도 임계값')
ON DUPLICATE KEY UPDATE setting_id=setting_id;

-- ============================================================
-- 뷰 (add_column 반영: accuracy 포함)
-- ============================================================
DROP VIEW IF EXISTS v_event_details;
CREATE VIEW v_event_details AS
SELECT
    el.*,
    u.name AS user_name,
    et.type_name AS event_type,
    et.severity
FROM event_logs el
JOIN users u ON el.user_id = u.user_id
JOIN event_types et ON el.event_type_id = et.event_type_id;

-- ============================================================
-- 완료
-- ============================================================
SELECT 'home_safe_user DB 및 homesafeusr 계정 설정 완료.' AS Status;
SELECT User, Host FROM mysql.user WHERE User = 'homesafeusr';
