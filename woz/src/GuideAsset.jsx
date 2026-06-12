import { useState } from "react";
import styles from "./GuideAsset.module.css";

/**
 * GuideAsset — '설명 자료 슬롯' 한 개를 렌더한다(레퍼런스 슬롯과 별개, '제안 설명'용).
 *
 * asset: { type: "svg"|"ai_example"|"backbone_3d", ref_id, label, caption }
 *   - 이미지 소스는 `${apiBase}/guide-asset/{ref_id}` (floor:* 는 백엔드가 도식 SVG를 인라인 반환).
 *   - type 배지를 항상 함께 보여, '결정적 도해 / 기하 참고 / AI 일러스트' 중 무엇인지 알린다(신뢰 서사 보호).
 *   - AI 예시에는 "AI가 그린 예시" 주석을 덧붙여 실제 참고작과 섞이지 않게 한다.
 * 한 번에 *하나만* 보여준다. swaps(같은 축의 다른 후보)가 있으면 'type 스왑'으로 바꿔볼 수 있다.
 * asset 이 없으면 아무것도 그리지 않는다.
 */
const BADGE = {
  svg: { text: "도식", cls: "badgeSvg" },
  backbone_3d: { text: "3D 참고", cls: "badge3d" },
  ai_example: { text: "AI 예시", cls: "badgeAi" },
};

const GuideAsset = ({ asset, apiBase = "", swaps = [] }) => {
  const all = asset ? [asset, ...swaps.filter((s) => s.ref_id !== asset.ref_id)] : [];
  const [i, setI] = useState(0);
  if (!all.length) return null;

  const a = all[i];
  const badge = BADGE[a.type] || BADGE.svg;
  const src = `${apiBase}/guide-asset/${encodeURIComponent(a.ref_id)}`;

  return (
    <figure className={styles.wrap}>
      <div className={styles.frame}>
        <img className={styles.img} src={src} alt={a.caption || badge.text} loading="lazy" />
        <span className={`${styles.badge} ${styles[badge.cls]}`}>{badge.text}</span>
      </div>
      {a.caption && <figcaption className={styles.cap}>{a.caption}</figcaption>}
      {a.type === "ai_example" && (
        <p className={styles.aiNote}>AI가 그린 예시예요 — 실제 참고작이 아니라 느낌 참고용이에요.</p>
      )}
      {all.length > 1 && (
        <button
          type="button"
          className={styles.swap}
          onClick={() => setI((p) => (p + 1) % all.length)}
        >
          다른 예시 보기 ({i + 1}/{all.length})
        </button>
      )}
    </figure>
  );
};

export default GuideAsset;
