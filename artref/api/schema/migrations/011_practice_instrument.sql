-- 011_practice_instrument.sql
-- 계측기 버전 태그: SUBJECT_MASK 등 '측정 가능 영역'을 바꾸는 변경은 정확도 개선이 아니라
-- 계측 장치 변경이다. 그러면 학생의 "명도 폭이 늘었다"가 실력 변화인지 계측 변화인지 섞인다.
-- practice_log 행에 그때의 instrument_version 을 박아, 성장 비교가 변경 경계를 넘지 않게 한다.
-- nullable: 과거 행은 NULL(=마스크 이전 계측). 컬럼이 이미 있으면 1060 으로 건너뜀(재실행 안전).
ALTER TABLE practice_log
  ADD COLUMN instrument_version VARCHAR(32) NULL;
