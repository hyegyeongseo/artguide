-- 008_widen_ref_id.sql  (구 007_widen_ref_id.sql — 007 번호 충돌 해소를 위해 008 로 리넘버)
-- ref_id 가 UUID(36) 기준 CHAR(36) 이었으나, AI 예제 ref_id(ai_<축>_<매체>_<트랙>_NNN)는 최대 ~51자라 초과.
-- 조직형 ref_id 수용을 위해 관련 컬럼을 VARCHAR(96) 으로 확장. (FK 제약 없음 → 독립 ALTER 안전)
-- ai_qc_audit 는 005 에서 생성되므로 005 뒤(=008)에 적용돼야 안전.
ALTER TABLE reference_images MODIFY ref_id       VARCHAR(96);
ALTER TABLE adoption_log     MODIFY reference_id  VARCHAR(96);
ALTER TABLE ai_qc_audit      MODIFY ref_id        VARCHAR(96);
