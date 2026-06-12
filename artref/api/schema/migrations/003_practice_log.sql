-- 003_practice_log.sql
-- 로드맵/진척 레이어의 원천 로그.
-- "시도해봤어요 / 나중에" 버튼과 진단 결과가 여기에 누적되고,
-- pipeline/roadmap.py 가 이걸 읽어 '현재 단계 → 다음 연습 → 다음 목표'를 만든다.
-- 사용자 식별이 없으면 user_id = 'anon' (단일 사용자/세션 기준으로도 동작).

CREATE TABLE IF NOT EXISTS practice_log (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id     VARCHAR(64) NOT NULL DEFAULT 'anon',
  sub_problem VARCHAR(64) NOT NULL,
  action      ENUM('seen','tried','later') NOT NULL,  -- seen=진단노출, tried=시도, later=나중에
  confidence  FLOAT,                                   -- 그때 진단 신뢰도(측정이면 높음)
  guide_id    CHAR(36),
  ts          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX (user_id, sub_problem),
  INDEX (user_id, ts)
);
