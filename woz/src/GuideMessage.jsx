import { useState } from "react";
import styles from "./GuideMessage.module.css";

/**
 * GuideMessage — 4카드 가이드 출력 컴포넌트
 *
 * 1. 관찰 → 2. 읽히는 느낌 → 3. 이번에 딱 하나 → 4. 레퍼런스
 *
 * 베타 검증 후에는 ChatPage.jsx에서 assistant 메시지의 mode === "coach"일 때
 * 기존 assistantBubble 대신 이 컴포넌트를 렌더하면 됨.
 *
 * Props:
 *  - observation, effect, practice, referenceWhy: 카드 본문 텍스트
 *  - references: [{ id, url }] 0~3개
 *  - subProblem: 이 가이드의 sub_problem id (예: "hand_structure")
 *      → /construction/<subProblem>.svg 구축 다이어그램을 3번 카드에 표시.
 *      값이 없거나 파일이 없으면 자동으로 숨김(앱 안 깨짐).
 *  - userMessage: 상단 컨텍스트 띠에 표시
 *  - onPracticeAttempted / onPracticeDeferred: 연습 시도 콜백
 *  - onRefClicked(idx, ref): 레퍼런스 카드 클릭
 *  - onRefPinned(idx, ref, isPinned): 핀 토글
 *  - onRefFeedback(type): "helpful" | "not_helpful" | "other_request"
 */
const GuideMessage = ({
  observation,
  effect,
  practice,
  referenceWhy,
  references = [],
  subProblem,
  userMessage,
  onPracticeAttempted,
  onPracticeDeferred,
  onRefClicked,
  onRefPinned,
  onRefFeedback,
}) => {
  const [practiceState, setPracticeState] = useState(null);
  const [pinnedIds, setPinnedIds] = useState(() => new Set());
  const [refFeedback, setRefFeedback] = useState(null);

  const handlePracticeAttempt = () => {
    if (practiceState === "attempted") return;
    setPracticeState("attempted");
    onPracticeAttempted?.();
  };

  const handlePracticeDefer = () => {
    if (practiceState === "deferred") return;
    setPracticeState("deferred");
    onPracticeDeferred?.();
  };

  const handlePinToggle = (idx, ref) => {
    setPinnedIds((prev) => {
      const next = new Set(prev);
      const isPinned = next.has(idx);
      if (isPinned) next.delete(idx);
      else next.add(idx);
      onRefPinned?.(idx, ref, !isPinned);
      return next;
    });
  };

  const handleRefFeedback = (type) => {
    setRefFeedback(type);
    onRefFeedback?.(type);
  };

  return (
    <div className={styles.guideStack}>
      {userMessage && (
        <div className={styles.contextStrip}>
          <MessageIcon />
          <span>업로드한 그림 · {userMessage}</span>
        </div>
      )}

      {/* Card 1 — 관찰 */}
      <div className={styles.card}>
        <div className={styles.stepBadge}>
          <EyeIcon />
          <span>1. 분석</span>
        </div>
        <p className={styles.cardBody}>
          {observation || "(관찰 내용이 여기 표시됩니다)"}
        </p>
      </div>

      <Arrow />

      {/* Card 2 — 읽히는 느낌 */}
      <div className={styles.card}>
        <div className={styles.stepBadge}>
          <BulbIcon />
          <span>2. 읽히는 느낌</span>
        </div>
        <p className={styles.cardBody}>
          {effect || "(읽히는 느낌이 여기 표시됩니다)"}
        </p>
      </div>

      <Arrow />

      {/* Card 3 — 이번에 딱 하나 (강조) */}
      <div className={`${styles.card} ${styles.cardEmphasized}`}>
        <div className={`${styles.stepBadge} ${styles.stepBadgeAccent}`}>
          <TargetIcon />
          <span>3. 한 끗 포인트</span>
        </div>
        <p className={styles.cardBody}>
          {practice || "(다음 연습이 여기 표시됩니다)"}
        </p>

        {/* 구축 다이어그램 — sub_problem 에 맞는 교육 도식 (있을 때만) */}
        <ConstructionDiagram subProblem={subProblem} />

        <div className={styles.practiceActions}>
          <button
            type="button"
            className={`${styles.practiceBtnPrimary} ${
              practiceState === "attempted" ? styles.practiceBtnDone : ""
            }`}
            onClick={handlePracticeAttempt}
          >
            {practiceState === "attempted" ? "✓ 시도해봤어요" : "시도해봤어요"}
          </button>
          <button
            type="button"
            className={`${styles.practiceBtn} ${
              practiceState === "deferred" ? styles.practiceBtnDeferred : ""
            }`}
            onClick={handlePracticeDefer}
          >
            나중에
          </button>
        </div>
      </div>

      <Arrow />

      {/* Card 4 — 레퍼런스 */}
      <div className={styles.card}>
        <div className={styles.stepBadge}>
          <PhotoIcon />
          <span>4. 추천 레퍼런스</span>
        </div>

        <div className={styles.whyBox}>
          <strong>왜 이 레퍼런스인가:</strong>{" "}
          {referenceWhy || "(설명이 여기 표시됩니다)"}
        </div>

        <div className={styles.refGrid}>
          {references.length === 0 && (
            <span className={styles.refPlaceholder}>
              아직 표시할 레퍼런스가 없어요 (관찰·연습부터 진행)
            </span>
          )}
          {references.map((ref, i) => {
            const pinned = pinnedIds.has(i + 1);
            return (
              <div
                key={ref.id ?? i}
                className={styles.refItem}
                onClick={() => ref && onRefClicked?.(i + 1, ref)}
              >
                {ref?.url ? (
                  <img
                    src={ref.url}
                    alt={`레퍼런스 ${i + 1}`}
                    className={styles.refImage}
                    loading="lazy"
                  />
                ) : (
                  <span className={styles.refPlaceholder}>
                    <PhotoIcon size={28} />
                  </span>
                )}
                <button
                  type="button"
                  className={`${styles.pinBtn} ${
                    pinned ? styles.pinBtnActive : ""
                  }`}
                  onClick={(e) => {
                    e.stopPropagation();
                    handlePinToggle(i + 1, ref);
                  }}
                  aria-label={pinned ? "핀 해제" : "핀하기"}
                >
                  <PinIcon />
                </button>
              </div>
            );
          })}
        </div>

        <div className={styles.refFeedback}>
          <button
            type="button"
            className={refFeedback === "helpful" ? styles.feedbackClicked : ""}
            onClick={() => handleRefFeedback("helpful")}
          >
            <ThumbsUpIcon /> 도움됨
          </button>
          <button
            type="button"
            className={
              refFeedback === "not_helpful" ? styles.feedbackClicked : ""
            }
            onClick={() => handleRefFeedback("not_helpful")}
          >
            <ThumbsDownIcon /> 안 맞음
          </button>
          <button
            type="button"
            className={
              refFeedback === "other_request" ? styles.feedbackClicked : ""
            }
            onClick={() => handleRefFeedback("other_request")}
          >
            <RefreshIcon /> 다른 레퍼런스
          </button>
        </div>
      </div>
    </div>
  );
};

const Arrow = () => (
  <div className={styles.arrow} aria-hidden="true">
    <ChevronDownIcon />
  </div>
);

/* ===== 구축 다이어그램 ===== */
/* /construction/<subProblem>.svg 를 표시. 값 없음/404면 자동 숨김.
   CSS 모듈 수정 없이 동작하도록 인라인 스타일 사용. SVG는 woz/public/construction/ 에 둘 것. */
const ConstructionDiagram = ({ subProblem }) => {
  const [failed, setFailed] = useState(false);
  if (!subProblem || failed) return null;
  return (
    <figure style={diagramStyles.box}>
      <img
        src={`/construction/${subProblem}.svg`}
        alt="구축 가이드 다이어그램"
        style={diagramStyles.img}
        loading="lazy"
        onError={() => setFailed(true)}
      />
      <figcaption style={diagramStyles.cap}>구축 가이드</figcaption>
    </figure>
  );
};

const diagramStyles = {
  box: { margin: "12px 0 4px", textAlign: "center" },
  img: {
    width: "100%",
    maxWidth: 320,
    aspectRatio: "1 / 1",
    background: "#fff",
    border: "1px solid #eee",
    borderRadius: 10,
    padding: 8,
    boxSizing: "border-box",
  },
  cap: { fontSize: 12, color: "#8a8f98", marginTop: 4 },
};

/* ===== Icons (inline SVG — 기존 코드 스타일과 일치) ===== */

const EyeIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
);

const BulbIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 18h6M10 22h4M12 2a7 7 0 0 1 4 12.7c-.5.4-1 1-1 1.6V18h-6v-1.7c0-.6-.5-1.2-1-1.6A7 7 0 0 1 12 2z" />
  </svg>
);

const TargetIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <circle cx="12" cy="12" r="6" />
    <circle cx="12" cy="12" r="2" />
  </svg>
);

const PhotoIcon = ({ size = 14 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <circle cx="8.5" cy="8.5" r="1.5" />
    <path d="M21 15l-5-5L5 21" />
  </svg>
);

const ChevronDownIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="6 9 12 15 18 9" />
  </svg>
);

const MessageIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5z" />
  </svg>
);

const PinIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
    <path d="M14 4l6 6-1.5 1.5-2 2L13 17 9 13l-2 5-3 3 3-3 5-2-4-4 3.5-3.5 2-2L14 4z" />
  </svg>
);

const ThumbsUpIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M7 11v8a2 2 0 0 0 2 2h7.5a2 2 0 0 0 2-1.5l1.5-6.5a2 2 0 0 0-2-2.5h-4l.7-3.5a2 2 0 0 0-2-2.5L10 8 7 11z" />
  </svg>
);

const ThumbsDownIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17 13V5a2 2 0 0 0-2-2H7.5a2 2 0 0 0-2 1.5L4 11a2 2 0 0 0 2 2.5h4l-.7 3.5a2 2 0 0 0 2 2.5L14 16l3-3z" />
  </svg>
);

const RefreshIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="23 4 23 10 17 10" />
    <polyline points="1 20 1 14 7 14" />
    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
  </svg>
);

export default GuideMessage;
