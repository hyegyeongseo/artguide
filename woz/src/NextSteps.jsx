import styles from "./NextSteps.module.css";
import GuideAsset from "./GuideAsset";

/**
 * NextSteps — '앞으로 할 것' 패널.
 *
 * GuideResponse.next_steps(백엔드가 로드맵에서 결정적으로 채움)를 렌더한다.
 * 완성작(finished=true)이면 '고칠 점'이 아니라 '앞으로 키울 것'을 앞세우는 자세로 강조한다.
 *
 * next: { focus, focus_practice, next_goal, next_goal_practice, recurring[], why }
 *   - focus / next_goal / recurring 항목은 sub_problem id → SUB_LABELS로 한글 표시.
 *   - focus_practice / why / next_goal_practice 는 이미 한글 문장이라 그대로 표시.
 * next가 없거나 focus가 비면 아무것도 렌더하지 않는다(앱 안 깨짐).
 */
const SUB_LABELS = {
  weight_balance: "무게중심",
  foreshortening: "단축(투시)",
  proportion: "비율",
  action_line: "동세",
  joint_articulation: "관절",
  hand_structure: "손 구조",
  value_structure: "명암",
  composition_balance: "구도",
  color_harmony: "색 조화",
  light_direction: "빛 방향",
  linear_perspective: "선원근",
  atmospheric_perspective: "대기원근",
  depth_layering: "공간 깊이",
  horizon_placement: "지평선 배치",
};
const labelOf = (id) => SUB_LABELS[id] || id;

const NextSteps = ({ next, finished = false, apiBase = "" }) => {
  if (!next || !next.focus) return null;
  const {
    focus,
    focus_practice,
    next_goal,
    next_goal_practice,
    recurring = [],
    why,
    focus_asset,
  } = next;

  return (
    <section className={`${styles.wrap} ${finished ? styles.wrapFinished : ""}`}>
      <div className={styles.head}>
        <CompassIcon />
        <span>{finished ? "완성작이네요 — 앞으로 키워볼 것" : "5. 앞으로 해야 할 것"}</span>
      </div>

      <div className={styles.focusRow}>
        <span className={styles.tag}>지금 집중</span>
        <span className={styles.focusName}>{labelOf(focus)}</span>
      </div>
      {focus_practice && <p className={styles.practice}>{focus_practice}</p>}
      {focus_asset && <GuideAsset asset={focus_asset} apiBase={apiBase} />}

      {next_goal && (
        <div className={styles.nextGoalRow}>
          <span className={styles.tag}>다음 목표</span>
          <span className={styles.goalName}>{labelOf(next_goal)}</span>
          {next_goal_practice && (
            <span className={styles.goalHint}>{next_goal_practice}</span>
          )}
        </div>
      )}

      {why && <p className={styles.why}>{why}</p>}

      {/* 성장 단계 확인용 — 하단 독립 섹션(최근 같이 본 부분) */}
      {recurring.length > 0 && (
        <div className={styles.recentRow}>
          <span className={styles.recentLabel}>최근 같이 본 부분</span>
          <div className={styles.chips}>
            {recurring.map((id) => (
              <span key={id} className={styles.chip}>
                {labelOf(id)}
              </span>
            ))}
          </div>
        </div>
      )}
    </section>
  );
};

const CompassIcon = () => (
  <svg
    width="14"
    height="14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <circle cx="12" cy="12" r="10" />
    <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" />
  </svg>
);

export default NextSteps;
