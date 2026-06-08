import { useRef, useState } from "react";
import GuideMessage from "./GuideMessage";
import styles from "./GuideEntry.module.css";

/**
 * GuideEntry — 정식(출시용) 사용자 입구.
 *
 * 흐름: 그림 업로드 + "어떤 점이 마음에 걸리나요?" → POST /guide(multipart)
 *       → GuideResponse(mode=coach|redirect|clarify|refused) → GuideMessage 렌더.
 * 레퍼런스는 reference_ids → `${API_BASE}/image/{id}` 로 표시(백엔드 /image 302).
 * 상호작용은 /adopt 로 로깅(검증 지표).
 *
 * WoZ(운영자 수동) 페이지와 별개. 검증 통과 후 이 화면을 제품 입구로 사용.
 *
 * 백엔드 주소: 환경변수 VITE_API_BASE 우선, 없으면 localhost:8000.
 */
const API_BASE =
  (typeof import.meta !== "undefined" &&
    import.meta.env &&
    import.meta.env.VITE_API_BASE) ||
  "http://localhost:8000";

// 칩 = 사용자 언어 라벨 + 실제 전송 message. message는 라우터 LEXICON 키워드를 포함해
// taxonomy 항목이 surface되도록 정렬(주석은 매핑되는 sub_problem).
const CHIPS = [
  { label: "손이 어색해요", message: "손이 어색해요" }, // 손 → hand_structure
  { label: "동세가 약해요", message: "동세가 약해요" }, // 동세 → action_line
  { label: "비율이 안 맞아요", message: "비율이 안 맞아요" }, // 비율 → proportion
  { label: "입체감이 없어요", message: "명암 대비가 약해 입체감이 없어요" }, // 명암·대비 → value_structure
  { label: "구도가 밋밋해요", message: "구도가 밋밋해요" }, // 구도 → composition_balance
  { label: "색이 따로 놀아요", message: "색이 따로 놀아요" }, // 색 → color_harmony
];

const ACCEPT = ["image/png", "image/jpeg", "image/webp"];

const GuideEntry = () => {
  const fileInput = useRef(null);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState("idle"); // idle | loading | done | error
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [guideId, setGuideId] = useState(null);
  const [dragOver, setDragOver] = useState(false);

  const pickFile = (f) => {
    if (!f) return;
    if (!ACCEPT.includes(f.type)) {
      setError("PNG · JPG · WEBP만 올려주세요.");
      return;
    }
    setError(null);
    setFile(f);
    setPreview((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return URL.createObjectURL(f);
    });
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    pickFile(e.dataTransfer.files && e.dataTransfer.files[0]);
  };

  const reset = () => {
    if (preview) URL.revokeObjectURL(preview);
    setFile(null);
    setPreview(null);
    setMessage("");
    setResult(null);
    setGuideId(null);
    setStatus("idle");
    setError(null);
  };

  const adoptRaw = (gid, referenceId, event) => {
    if (!gid || !referenceId) return;
    fetch(`${API_BASE}/adopt`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        guide_id: gid,
        reference_id: referenceId,
        persona: "unknown", // /guide가 ref별 persona/source_type을 돌려주면 채움(후속)
        source_type: "unknown",
        event,
      }),
    }).catch(() => {});
  };
  const adopt = (referenceId, event) => adoptRaw(guideId, referenceId, event);

  const submit = async () => {
    if (!file) {
      setError("먼저 그림을 올려주세요.");
      return;
    }
    setStatus("loading");
    setError(null);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("message", message);
      const res = await fetch(`${API_BASE}/guide`, { method: "POST", body: fd });
      if (!res.ok) throw new Error(`서버 오류 (${res.status})`);
      const data = await res.json();
      // 서버가 발급한 guide_id 사용(노출은 서버가 sub_problem과 함께 기록). 없으면 클라 생성 폴백.
      const gid =
        data.guide_id ||
        (typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : String(Date.now()));
      setResult(data);
      setGuideId(gid);
      setStatus("done");
    } catch (e) {
      setError(
        (e && e.message) ||
          "요청에 실패했어요. 백엔드가 켜져 있는지 확인해주세요."
      );
      setStatus("error");
    }
  };

  const renderResult = () => {
    if (!result) return null;
    if (result.mode === "coach") {
      const block = (result.blocks && result.blocks[0]) || {};
      const refs = (block.reference_ids || []).map((id) => ({
        id,
        url: `${API_BASE}/image/${id}`,
      }));
      return (
        <GuideMessage
          observation={block.observation}
          effect={block.effect}
          practice={result.one_thing || block.direction}
          referenceWhy={
            result.synthesis || "이 관찰과 연결되는 참고 이미지예요."
          }
          references={refs}
          userMessage={message}
          onRefClicked={(idx, ref) => ref && adopt(ref.id, "clicked")}
          onRefPinned={(idx, ref, isPinned) =>
            ref && isPinned && adopt(ref.id, "saved")
          }
          onRefFeedback={(type) => {
            if (type === "helpful" && refs[0]) adopt(refs[0].id, "liked");
          }}
        />
      );
    }
    // redirect | clarify | refused
    return (
      <div className={styles.notice}>
        {result.message || "다시 시도해 주세요."}
      </div>
    );
  };

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.logo}>
          <PenIcon />
        </div>
        <div>
          <div className={styles.title}>그림 한 끗</div>
          <div className={styles.subtitle}>
            한 번에 딱 하나씩, 그림을 같이 봐드려요
          </div>
        </div>
      </header>

      <div className={styles.panel}>
        <div
          className={`${styles.dropzone} ${
            dragOver ? styles.dropzoneOver : ""
          } ${preview ? styles.dropzoneFilled : ""}`}
          onClick={() => fileInput.current && fileInput.current.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
        >
          {preview ? (
            <>
              <img
                src={preview}
                className={styles.previewImg}
                alt="업로드한 그림"
              />
              <button
                type="button"
                className={styles.removeBtn}
                onClick={(e) => {
                  e.stopPropagation();
                  reset();
                }}
                aria-label="그림 지우기"
              >
                ✕
              </button>
            </>
          ) : (
            <div className={styles.dropInner}>
              <ImageIcon />
              <div className={styles.dropText}>그림을 올려주세요</div>
              <div className={styles.dropHint}>
                클릭하거나 끌어다 놓기 · PNG · JPG · WEBP
              </div>
            </div>
          )}
          <input
            ref={fileInput}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            hidden
            onChange={(e) => pickFile(e.target.files && e.target.files[0])}
          />
        </div>

        <label className={styles.qLabel}>어떤 점이 마음에 걸리나요?</label>
        <input
          className={styles.qInput}
          type="text"
          placeholder="예: 손이 이상해요"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
        />

        <div className={styles.chips}>
          {CHIPS.map((c) => (
            <button
              key={c.label}
              type="button"
              className={`${styles.chip} ${
                message === c.message ? styles.chipActive : ""
              }`}
              onClick={() => setMessage(c.message)}
            >
              {c.label}
            </button>
          ))}
        </div>

        {error && <div className={styles.error}>{error}</div>}

        <button
          type="button"
          className={styles.submit}
          disabled={status === "loading"}
          onClick={submit}
        >
          {status === "loading" ? "가이드 만드는 중…" : "가이드 받기"}
        </button>
      </div>

      {status === "done" && (
        <div className={styles.resultWrap}>
          {renderResult()}
          <button type="button" className={styles.againBtn} onClick={reset}>
            다른 그림 보기
          </button>
        </div>
      )}
    </div>
  );
};

/* ===== Icons (inline SVG — GuideMessage와 같은 스타일) ===== */

const PenIcon = () => (
  <svg
    width="20"
    height="20"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M12 19l7-7 3 3-7 7-3-3z" />
    <path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z" />
    <path d="M2 2l7.586 7.586" />
    <circle cx="11" cy="11" r="2" />
  </svg>
);

const ImageIcon = () => (
  <svg
    width="40"
    height="40"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <circle cx="8.5" cy="8.5" r="1.5" />
    <path d="M21 15l-5-5L5 21" />
  </svg>
);

export default GuideEntry;
