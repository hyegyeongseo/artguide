-- 002_library_columns.sql  (MySQL 8.4)
--
-- 목적 1) region/category/body_type/gender 를 MySQL에도 영속화(무손실 재색인).
-- 목적 2) svg_key (Freestyle 구축선 SVG 저장 키, Phase 4).

ALTER TABLE reference_images ADD COLUMN region    VARCHAR(32);
ALTER TABLE reference_images ADD COLUMN category  VARCHAR(64);
ALTER TABLE reference_images ADD COLUMN body_type VARCHAR(64);
ALTER TABLE reference_images ADD COLUMN gender    VARCHAR(32);
ALTER TABLE reference_images ADD COLUMN svg_key   VARCHAR(512);
CREATE INDEX idx_ref_region ON reference_images (region);
