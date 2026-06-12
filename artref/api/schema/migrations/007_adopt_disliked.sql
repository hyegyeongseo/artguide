-- 007_adopt_disliked.sql
-- 레퍼런스 '싫어요' 신호를 받기 위해 adoption_log.event ENUM에 'disliked' 추가.
-- (앱은 main.py의 _ensure_adopt_schema()로 기동 시 자동 확장도 하므로, 이 파일은 정식 마이그레이션 기록용.)
ALTER TABLE adoption_log
  MODIFY event ENUM('shown','clicked','saved','liked','disliked') NOT NULL;
