-- 009_observable_action.sql
-- 관측층(observability) 신호 추가: practice_log.action 에 'observable' 값 도입.
-- 'seen'(flagged = 약점으로 떴음)과 분리해, 업로드마다 '측정 가능했던 축'(주제 등장)을 기록한다.
-- roadmap 이 '부재(안 그림) → steady'를 '개선(그렸는데 덜 걸림)'과 구분하는 근거가 된다.
-- ENUM 끝에 값 추가는 MySQL 에서 메타데이터 변경(빠름, 데이터 재작성 없음). 같은 정의 재실행도 안전.
ALTER TABLE practice_log
  MODIFY COLUMN action ENUM('seen','tried','later','observable') NOT NULL;
