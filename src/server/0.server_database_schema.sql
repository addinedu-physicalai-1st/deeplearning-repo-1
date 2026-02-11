-- 데이터베이스 생성
-- 1) 기존 DB 삭제 (있으면 삭제)
SET FOREIGN_KEY_CHECKS = 0;
DROP DATABASE IF EXISTS home_safe_admin;
SET FOREIGN_KEY_CHECKS = 1;

-- 2) 계정 삭제 후 재생성
DROP USER IF EXISTS 'homesafeadmin'@'%';
CREATE USER 'homesafeadmin'@'%' IDENTIFIED BY 'admin1234!';

-- 3) DB 생성 및 권한 부여
CREATE DATABASE homesafeadmin CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON homesafeadmin.* TO 'homesafeadmin'@'%';

FLUSH PRIVILEGES;

USE home_safe_admin; 
-- ============================================================

CREATE TABLE `users` (
    -- 단순 순번: 자동으로 1씩 증가하며 데이터의 고유 식별자가 됨
    `index_no` INT NOT NULL AUTO_INCREMENT,
    
    -- 장치 고유 ID (입력 시 직접 입력)
    `device_id` VARCHAR(64) NOT NULL,
    
    -- 아이디 (최대 16자리)
    `user_id` VARCHAR(16) NOT NULL,
    
    -- 비밀번호 (개발용 평문 저장, 최대 12자리)
    `password` VARCHAR(12) NOT NULL,
    
    -- 사용자 정보
    `name` VARCHAR(50) NOT NULL,
    `gender` ENUM('M', 'F') DEFAULT 'M',
    `blood_type` VARCHAR(5),
    `address` TEXT,
    `birth_date` DATE,
    `phone` VARCHAR(20),
    `emergency_phone` VARCHAR(20),
    
    -- 사용자 유형 (일반사용자: 'NORMAL', 감시모드 사용자: 'MONITOR')
    `user_type` ENUM('NORMAL', 'MONITOR') DEFAULT 'NORMAL',
    
    -- 감시모드 허용 ID (부모님의 user_id 저장)
    `monitor_target_id` VARCHAR(16),
    
    -- 생성 및 수정 시간
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- 제약 조건
    PRIMARY KEY (`index_no`),
    UNIQUE KEY `uk_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

USE home_safe_admin;

-- 이미 있을 수 있으니 안전하게 삭제 후 생성 
DROP TABLE IF EXISTS admin_users;

CREATE TABLE admin_users (
    admin_no    INT AUTO_INCREMENT PRIMARY KEY,          -- 내부 PK
    admin_id    VARCHAR(50)  NOT NULL UNIQUE,            -- 로그인용 ID
    admin_pw    VARCHAR(255) NOT NULL,                   -- 로그인용 PW (현재는 평문/샘플)
    admin_role  ENUM('Master','Manager','Viewer') NOT NULL DEFAULT 'Manager', -- 관리자 등급
    is_active   TINYINT(1) NOT NULL DEFAULT 1,           -- 사용 여부
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


USE home_safe_admin;

INSERT INTO admin_users (admin_id, admin_pw, admin_role, is_active)
VALUES ('admin', 'admin123', 'Master', 1)
ON DUPLICATE KEY UPDATE
    admin_pw  = VALUES(admin_pw),
    admin_role = VALUES(admin_role),
    is_active = VALUES(is_active);


-- ============================================================
-- 3. 응급 이벤트 테이블 (실시간 알람 수신 시 영상 저장 및 이벤트 기록)
-- ============================================================
USE home_safe_admin;

DROP TABLE IF EXISTS emergency_events;

CREATE TABLE emergency_events (
    event_id        INT NOT NULL AUTO_INCREMENT,
    user_id         VARCHAR(16) NOT NULL,
    device_id       VARCHAR(64),
    event_type      VARCHAR(32) DEFAULT 'ALERT',
    message         VARCHAR(255),
    video_path      VARCHAR(512),
    client_timestamp VARCHAR(50),
    raw_payload     JSON,
    received_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (event_id),
    INDEX idx_user_id (user_id),
    INDEX idx_received_at (received_at),
    INDEX idx_event_type (event_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
