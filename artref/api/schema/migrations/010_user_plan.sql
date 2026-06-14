-- 010_user_plan.sql — Layer 3 에이전트가 고른 '다음 단계 계획'(사용자·트랙당 1행).
-- guide 파이프라인이 업로드마다 갱신(쓰기), /roadmap 이 읽어 agent_plan 으로 노출(읽기).
-- AGENT_PLAN 켜졌을 때만 채워진다. roadmap._save_plan/_load_plan 이 사용.
-- 코드가 CREATE TABLE IF NOT EXISTS 로 자동 생성하지만, 운영 스키마 기록을 위해 마이그레이션으로도 남긴다.
CREATE TABLE IF NOT EXISTS user_plan (
  user_id     VARCHAR(64) NOT NULL,
  track       VARCHAR(32) NOT NULL DEFAULT '',
  focus       VARCHAR(48) NOT NULL,                          -- 에이전트가 고른 현재 집중 축
  next_goal   VARCHAR(48) NULL,                              -- 그 다음 목표 축(커리큘럼상)
  reason_code VARCHAR(48) NOT NULL DEFAULT 'rule_default',   -- 선택 사유 코드(plan_next)
  candidates  TEXT        NULL,                              -- 고정 시점 후보 풀 스냅샷(JSON, 감사용)
  updated_at  TIMESTAMP   DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, track)
);
