-- 004_ai_example_source.sql
-- 생성형 AI 레퍼런스(ai_example)를 별도 source_type 으로 구분하기 위한 enum 확장.
-- 없으면 ingest(source_type="ai_example") 의 INSERT 가 깨진다. (museum/self_render/stock 기존 값 보존.)
ALTER TABLE reference_images
  MODIFY source_type ENUM('museum','self_render','stock','ai_example') NOT NULL;
