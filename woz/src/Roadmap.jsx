import { useState, useEffect } from "react";
import styles from "./Roadmap.module.css";

/**
 * Roadmap — '성장 흐름'을 보는 별도 화면(메인 가이드와 분리).
 *
 * GET /roadmap?user_id=&track= 를 그대로 렌더한다(백엔드 결정적 산출):
 *   progress{steady,total} · trend(약점 증감 방향) · current(지금 집중) · next_goal ·
 *   ladder[{status,tries,flagged,recurring,peer_active,flag_count}] · why.
 * 메인 UI는 스샷대로 단순하게 두고, 내부 성장 원리는 여기서 전부 확인 가능.
 */
const SUB_LABELS = {
  weight_balance: "무게중심", foreshortening: "단축(투시)", proportion: "비율",
  action_line: "동세", joint_articulation: "관절", hand_structure: "손 구조",
  value_structure: "명암", composition_balance: "구도", color_harmony: "색 조화",
  light_direction: "빛 방향", linear_perspective: "선원근",
  atmospheric_perspective: "대기원근", depth_layering: "공간 깊이",
  horizon_placement: "지평선 배치",
};
const labelOf = (id) => SUB_LABELS[id] || id;

const STATUS = {
  steady: { label: "자리잡음", cls: "stSteady" },
  improving: { label: "나아지는 중", cls: "stImproving" },
  practicing: { label: "연습 중", cls: "stPracticing" },
  new: { label: "아직", cls: "stNew" },
};
const TREND = {
  decreasing: { label: "약점이 줄고 있어요", cls: "trGood", icon: "↓" },
  increasing: { label: "약점이 조금 늘었어요", cls: "trWarn", icon: "↑" },
  steady: { label: "비슷하게 유지 중", cls: "trFlat", icon: "→" },
  new: { label: "아직 데이터가 적어요", cls: "trFlat", icon: "·" },
};

const Roadmap = ({ apiBase = "", userId, track }) => {
  const [data, setData] = useState(null);
  const [state, setState] = useState("loading"); // loading | done | error

  useEffect(() => {
    let live = true;
    setState("loading");
    const q = new URLSearchParams({ user_id: userId || "anon" });
    if (track) q.set("track", track);
    fetch(`${apiBase}/roadmap?${q.toString()}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((d) => live && (setData(d), setState("done")))
      .catch(() => live && setState("error"));
    return () => {
      live = false;
    };
  }, [apiBase, userId, track]);

  if (state === "loading") {
    return <div className={styles.muted}>성장 흐름을 불러오는 중…</div>;
  }
  if (state === "error" || !data) {
    return <div className={styles.muted}>성장 흐름을 불러오지 못했어요.</div>;
  }

  const { progress = {}, trend, current, next_goal, ladder = [], why, timeline = [] } = data;
  const total = progress.total || ladder.length || 1;
  const steady = progress.steady || 0;
  const tr = TREND[trend] || TREND.new;
  const tlMax = Math.max(1, ...timeline.map((x) => x.flagged_count || 0));

  return (
    <section className={styles.wrap}>
      <div className={styles.head}>
        <span className={styles.title}>성장 흐름</span>
        <span className={`${styles.trend} ${styles[tr.cls]}`}>
          {tr.icon} {tr.label}
        </span>
      </div>

      {/* 자리잡은 단계 진행 */}
      <div className={styles.progressRow}>
        <span className={styles.progressLabel}>
          자리잡은 단계 {steady}/{total}
        </span>
        <div className={styles.bar}>
          <div
            className={styles.barFill}
            style={{ width: `${Math.round((steady / total) * 100)}%` }}
          />
        </div>
      </div>

      {/* 그림마다 함께 본 부분 — 업로드별 약점 수(예전→최근). 점수 아님, 관찰 개수. */}
      {timeline.length >= 2 && (
        <div className={styles.timelineBox}>
          <div className={styles.timelineLabel}>그림마다 함께 본 부분</div>
          <div className={styles.bars}>
            {timeline.map((t, i) => {
              const h = Math.round(((t.flagged_count || 0) / tlMax) * 100);
              return (
                <div key={i} className={styles.barCol} title={`${t.flagged_count || 0}개`}>
                  <div
                    className={styles.barVal}
                    style={{ height: `${Math.max(h, 8)}%` }}
                  />
                </div>
              );
            })}
          </div>
          <div className={styles.barAxis}>
            <span>예전</span>
            <span>최근</span>
          </div>
        </div>
      )}

      {/* 지금 집중 + 다음 목표 */}
      {current && (
        <div className={styles.focusCard}>
          <span className={styles.tag}>지금 집중</span>
          <span className={styles.focusName}>{labelOf(current.sub_problem)}</span>
          {current.practice_prompt && (
            <p className={styles.practice}>{current.practice_prompt}</p>
          )}
          {next_goal && (
            <div className={styles.nextGoal}>
              <span className={styles.tagGhost}>다음 목표</span>
              <span>{labelOf(next_goal.sub_problem)}</span>
            </div>
          )}
        </div>
      )}

      {why && <p className={styles.why}>{why}</p>}

      {/* 전체 사다리 — 각 축의 상태/연습/재발/동료신호 */}
      <div className={styles.ladderLabel}>전체 흐름</div>
      <ul className={styles.ladder}>
        {ladder.map((r) => {
          const st = STATUS[r.status] || STATUS.new;
          return (
            <li key={r.sub_problem} className={styles.row}>
              <span className={styles.rowName}>{labelOf(r.sub_problem)}</span>
              <span className={`${styles.pill} ${styles[st.cls]}`}>{st.label}</span>
              <span className={styles.rowMeta}>
                {r.tries > 0 && <span className={styles.metaTry}>연습 {r.tries}회</span>}
                {r.recurring && <span className={styles.metaRecur}>자주 막힘</span>}
                {/* peer_active: 동료가 활성인데 이 축만 잠잠 → 해결 쪽 / 동료도 잠잠 → 주제 전환 */}
                {!r.flagged && r.peer_active === true && (
                  <span className={styles.metaResolved}>최근엔 안 보임</span>
                )}
                {!r.flagged && r.peer_active === false && (
                  <span className={styles.metaDormant}>요즘 덜 그림</span>
                )}
              </span>
            </li>
          );
        })}
      </ul>

      <p className={styles.foot}>
        평가가 아니라 ‘최근 무엇을 같이 봤는가’의 흐름이에요 — 단계·점수는 매기지 않아요.
      </p>
    </section>
  );
};

export default Roadmap;
