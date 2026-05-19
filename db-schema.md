# 数据库建表语句

> 数据库名：`food_health_platform`  
> 字符集：`utf8mb4`  
> 引擎：`InnoDB`  
> 建表顺序：`users` → `health_profiles` → `scan_history`

```sql
CREATE DATABASE IF NOT EXISTS food_health_platform
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE food_health_platform;

-- ============================================================
-- 1. 用户表
-- ============================================================
CREATE TABLE users (
    id            INT             NOT NULL AUTO_INCREMENT,
    email         VARCHAR(255)    NULL,
    username      VARCHAR(64)     NOT NULL,
    openid        VARCHAR(128)    NULL,
    phone         VARCHAR(32)     NULL,
    nickname      VARCHAR(64)     NULL,
    password_hash VARCHAR(255)    NULL,
    is_active     TINYINT(1)      NOT NULL DEFAULT 1,
    created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE INDEX ix_users_email (email),
    UNIQUE INDEX ix_users_username (username),
    UNIQUE INDEX ix_users_openid (openid),
    UNIQUE INDEX ix_users_phone (phone)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 2. 健康档案表
-- ============================================================
CREATE TABLE health_profiles (
    id                 INT           NOT NULL AUTO_INCREMENT,
    user_id            INT           NOT NULL,
    name               VARCHAR(64)   NULL,
    gender             VARCHAR(16)   NULL,
    birthday           DATE          NULL,
    height_cm          FLOAT         NULL,
    weight_kg          FLOAT         NULL,
    chronic_diseases   JSON          NOT NULL,
    allergies          JSON          NOT NULL,
    dietary_preferences JSON         NOT NULL,
    medication_notes   TEXT          NULL,
    emergency_contact  VARCHAR(64)   NULL,
    created_at         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE INDEX ix_health_profiles_user_id (user_id),
    CONSTRAINT fk_health_profiles_user FOREIGN KEY (user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 3. 扫描记录表
-- ============================================================
CREATE TABLE scan_history (
    id             INT           NOT NULL AUTO_INCREMENT,
    task_id        VARCHAR(64)   NOT NULL,
    user_id        INT           NOT NULL,
    image_path     VARCHAR(255)  NULL,
    question       TEXT          NULL,
    status         ENUM('pending','processing','completed','failed') NOT NULL DEFAULT 'pending',
    risk_level     ENUM('low','medium','high','unknown')            NOT NULL DEFAULT 'unknown',
    summary        TEXT          NULL,
    warnings       JSON          NOT NULL,
    suggestions    JSON          NOT NULL,
    extracted_text JSON          NOT NULL,
    raw_result     JSON          NOT NULL,
    error_message  TEXT          NULL,
    created_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE INDEX ix_scan_history_task_id (task_id),
    INDEX ix_scan_history_user_id (user_id),
    INDEX ix_scan_history_status (status),
    CONSTRAINT fk_scan_history_user FOREIGN KEY (user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```
