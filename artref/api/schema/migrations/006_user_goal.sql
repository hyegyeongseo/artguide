-- 006_user_goal.sql — N장 기준 '이번 목표' 고정/진급 상태(사용자·트랙당 1행).
-- roadmap._resolve_goal 이 사용. 코드가 CREATE TABLE IF NOT EXISTS 로 자동 생성하지만,
-- 운영 스키마 기록을 위해 마이그레이션으로도 남긴다.
CREATE TABLE IF NOT EXISTS user_goal (
  user_id        VARCHAR(64) NOT NULL,
  track          VARCHAR(32) NOT NULL DEFAULT '',
  sub_problem    VARCHAR(48) NOT NULL,            -- 현재 고정된 목표 축
  baseline_count INT         NOT NULL DEFAULT 0,  -- 고정 시점의 그 축 재발 횟수
  set_seq        INT         NOT NULL DEFAULT 0,  -- 고정 시점까지의 누적 업로드 수(N장 창 좌표)
  prev_achieved  VARCHAR(48) NULL,                -- 직전에 달성한 축(셀러브레이션용)
  advanced_seq   INT         NULL,                -- 진급이 일어난 업로드 수
  updated_at     TIMESTAMP   DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, track)
);
