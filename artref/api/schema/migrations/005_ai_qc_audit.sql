-- 005_ai_qc_audit.sql  (선택)
-- 생성형 이미지 QC 게이트의 통과/거부 감사 로그. 없어도 동작한다(ai_ingest 가 JSONL 로 폴백).
-- 적재 결정의 추적성(왜 reject 됐나 / 어떤 점수로 통과했나)을 DB 로 남기고 싶을 때만 실행.
CREATE TABLE IF NOT EXISTS ai_qc_audit (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  ref_id        CHAR(36) NULL,          -- 통과·적재면 채워짐, 거부면 NULL
  accepted      TINYINT(1) NOT NULL,
  concept       VARCHAR(512),
  intended_axes JSON,
  supports      JSON,                   -- 비전으로 검증된 축(= tags.supports)
  reasons       JSON,                   -- 거부 사유(통과면 [])
  scores        JSON,                   -- concept_cos / axis_cos / artwork_confidence 등
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX (accepted), INDEX (ref_id)
);
