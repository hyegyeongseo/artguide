import { useEffect, useMemo, useState } from "react";
import GuideMessage from "./GuideMessage";
import styles from "./WozTestPage.module.css";

/**
 * WoZ 테스트 페이지
 *
 * 운영자가 사용자 그림을 보고 WoZ 데이터셋의 시나리오를 골라 채워서
 * 사용자에게 보여주고 인터랙션을 기록하는 페이지.
 *
 * 백엔드 API 호출 없이 동작 — localStorage에 저장.
 * 베타 검증 후 GuideMessage 컴포넌트를 ChatPage.jsx로 이동하면 됨.
 *
 * 라우트 추가 예시 (App.jsx 또는 라우터 설정):
 *   <Route path="/woz-test" element={<WozTestPage />} />
 */

const STORAGE_KEY = "drawe_woz_state";

const SCENARIOS = {
  "F-2": {
    label: "F-2 손 엄지",
    userMessage: '"손이 이상해요"',
    card1: "오른손 엄지의 방향이 손바닥 평면과 다른 각도로 보이고, 그래서 손이 어느 방향을 향하는지 — 카메라 쪽인지 옆쪽인지 — 가 살짝 흐릿합니다.",
    card2: "손바닥의 방향이 인지되지 않아, 같은 손이라도 평면이 어디로 향하는지 읽기가 어려워집니다.",
    card3: "이번에는 손바닥의 상자만 먼저 그려보기 — 손가락 없이 손바닥 평면 하나만. 그 상자가 어느 방향을 보는지 확실히 잡힌 뒤, 엄지부터 그 평면의 옆면에서 시작되도록 추가하기.",
    card4Why: "엄지가 손바닥의 옆면에서 어떻게 시작되는지 — 평면 구조가 명확히 드러난 사례",
  },
  "A-1": {
    label: "A-1 정면 직립",
    userMessage: "",
    card1: "의도된 정적 자세가 아니라면, 머리에서 발끝까지가 거의 수직선 한 줄로 이어지고, 어깨선과 골반선이 같은 방향으로 평행하게 누워 있다는 점이 눈에 듭니다.",
    card2: "인물이 사진을 위해 잠시 멈춘 듯한 인상이라, 자세 자체로 전달하는 감정이 약해질 수 있습니다.",
    card3: "디테일 전에, 머리에서 지지발까지 한 번에 그은 S자 또는 C자 곡선 하나만 먼저 그어보기. 그 곡선 위에 나머지를 얹어보세요.",
    card4Why: "같은 직립 자세에서도 어깨/골반 기울기 차이만으로 동세가 살아나는 사례들",
  },
  "C-1": {
    label: "C-1 팔뻗기 단축",
    userMessage: "",
    card1: "카메라 쪽으로 뻗은 팔이 반대쪽 팔과 거의 같은 길이로 그려져 있고, 손의 크기도 비슷해 보입니다.",
    card2: "팔이 옆으로 뻗었는지 앞으로 뻗었는지가 잘 구분되지 않아, 공간감이 평평하게 읽힙니다.",
    card3: "뻗은 팔을 원통 마디 세 개 — 어깨에서 팔꿈치, 팔꿈치에서 손목, 손목에서 손끝 — 로 분해해서, 카메라에 가까운 마디는 크게, 먼 마디는 작게 그려보세요. 마디끼리 살짝 겹치게.",
    card4Why: "같은 팔뻗기 동작이 측면 시점과 정면 시점에서 어떻게 다르게 보이는지 비교",
  },
  "G-3": {
    label: "G-3 분위기 차가움",
    userMessage: '"따뜻한 느낌을 원했는데 그렇게 안 보여요"',
    card1: "의도하신 분위기(따뜻한 일상)와 실제 색감(차가운 톤 위주) 사이에 거리가 있고, 빛의 방향이나 강도도 따뜻한 시간대보다는 흐린 시간대에 가깝게 읽힙니다.",
    card2: "색의 기본 톤이 분위기를 가장 강하게 좌우하기 때문에, 다른 요소(구도·표정·소품)가 따뜻해도 차가운 색이 그것을 덮어쓸 수 있습니다.",
    card3: "주조색을 따뜻한 톤(주황·노랑)으로 한정해 팔레트만 다시 짜보세요. 그림의 형태는 그대로 두고 색만 바꿔도 분위기가 크게 달라집니다.",
    card4Why: "같은 일상 장면이 따뜻한 빛으로 어떻게 보이는지 — 색의 지배력을 확인하기 위함",
  },
  "H-4": {
    label: "H-4 다중 문제",
    userMessage: '"전체적으로 어색해요"',
    card1: "이 그림에는 같이 손볼 만한 부분이 여러 곳 있지만, 가장 먼저 영향이 큰 것은 자세의 동세 — 머리에서 발까지 흐르는 곡선이 거의 직선이라는 점입니다.",
    card2: "동세가 약하면 다른 부분(손·명도)을 다듬어도 전체적 어색함이 잘 줄어들지 않아요. 반대로 동세가 잡히면 나머지 문제가 덜 두드러져 보이기도 합니다.",
    card3: "한 번에 하나만 — 이번에는 동세부터. 머리에서 지지발까지 S자 곡선 하나를 그어두고, 그 위에 나머지를 얹어보세요. 손과 명도는 다음 그림이나 다음 단계에서.",
    card4Why: "기초 동세가 잡히면 다른 디테일이 따라 사는 사례들",
  },
};

const EMPTY_FORM = {
  sessionId: "",
  userMessage: "",
  card1: "",
  card2: "",
  card3: "",
  card4Why: "",
  ref1Url: "",
  ref2Url: "",
  ref3Url: "",
};

const WozTestPage = () => {
  const [mode, setMode] = useState("edit");
  const [form, setForm] = useState(EMPTY_FORM);
  const [log, setLog] = useState([]);
  const [previewStart, setPreviewStart] = useState(null);
  const [assessment, setAssessment] = useState({
    recognize: null,
    grounded: null,
    intent: null,
    submitted: false,
  });

  // Restore from localStorage on mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const data = JSON.parse(raw);
      if (data.form) setForm({ ...EMPTY_FORM, ...data.form });
      if (Array.isArray(data.log)) setLog(data.log);
    } catch (e) {
      // noop
    }
  }, []);

  // Persist
  const persist = (nextLog, nextForm) => {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          form: nextForm ?? form,
          log: nextLog ?? log,
        })
      );
    } catch (e) {
      // noop
    }
  };

  const updateForm = (key, value) => {
    const next = { ...form, [key]: value };
    setForm(next);
    persist(null, next);
  };

  const logEvent = (event, data) => {
    const entry = {
      timestamp: new Date().toISOString(),
      sessionId: form.sessionId || "unnamed",
      event,
      data: data ?? null,
    };
    if (previewStart) {
      entry.secondsSincePreview = Math.round(
        (Date.now() - previewStart) / 1000
      );
    }
    const next = [...log, entry];
    setLog(next);
    persist(next, null);
  };

  const handleModeSwitch = (next) => {
    if (next === "preview") {
      setPreviewStart(Date.now());
      setAssessment({
        recognize: null,
        grounded: null,
        intent: null,
        submitted: false,
      });
      setLog((curr) => {
        const entry = {
          timestamp: new Date().toISOString(),
          sessionId: form.sessionId || "unnamed",
          event: "preview_started",
          data: null,
        };
        const updated = [...curr, entry];
        persist(updated, null);
        return updated;
      });
    } else if (mode === "preview" && previewStart) {
      const dwellSec = Math.round((Date.now() - previewStart) / 1000);
      setLog((curr) => {
        const entry = {
          timestamp: new Date().toISOString(),
          sessionId: form.sessionId || "unnamed",
          event: "preview_ended",
          data: { dwellSeconds: dwellSec },
          secondsSincePreview: dwellSec,
        };
        const updated = [...curr, entry];
        persist(updated, null);
        return updated;
      });
      setPreviewStart(null);
    }
    setMode(next);
    window.scrollTo(0, 0);
  };

  const handleStartPreview = () => {
    if (!form.sessionId.trim()) {
      const ok = window.confirm("세션 ID가 비어 있어요. 그대로 진행할까요?");
      if (!ok) return;
    }
    handleModeSwitch("preview");
  };

  const setAssess = (key, value) =>
    setAssessment((a) => ({ ...a, [key]: value }));

  const submitAssessment = () => {
    const { recognize, grounded, intent } = assessment;
    if (recognize == null || grounded == null || intent == null) {
      window.alert("세 항목을 모두 선택해 주세요.");
      return;
    }
    logEvent("assessment", { recognize, grounded, intent });
    setAssessment((a) => ({ ...a, submitted: true }));
  };

  const loadScenario = (key) => {
    if (key === "clear") {
      const next = { ...form, ...EMPTY_FORM, sessionId: form.sessionId };
      setForm(next);
      persist(null, next);
      return;
    }
    const s = SCENARIOS[key];
    if (!s) return;
    const next = {
      ...form,
      userMessage: s.userMessage,
      card1: s.card1,
      card2: s.card2,
      card3: s.card3,
      card4Why: s.card4Why,
    };
    setForm(next);
    persist(null, next);
  };

  const newSession = () => {
    const ok = window.confirm(
      "새 세션을 시작할까요? 현재 폼이 비워집니다. (로그는 유지)"
    );
    if (!ok) return;
    setForm(EMPTY_FORM);
    persist(null, EMPTY_FORM);
  };

  const exportLog = () => {
    if (log.length === 0) {
      window.alert("내보낼 로그가 없어요.");
      return;
    }
    const blob = new Blob([JSON.stringify(log, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const date = new Date().toISOString().slice(0, 10);
    a.download = `drawe_woz_log_${date}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const clearLog = () => {
    if (!window.confirm("정말로 모든 로그를 지울까요?")) return;
    setLog([]);
    persist([], null);
  };

  const references = useMemo(
    () =>
      [form.ref1Url, form.ref2Url, form.ref3Url]
        .map((url, i) => (url.trim() ? { id: `ref${i + 1}`, url } : null))
        .filter(Boolean),
    [form.ref1Url, form.ref2Url, form.ref3Url]
  );

  // Log stats
  const stats = useMemo(() => {
    const events = {};
    const sessions = new Set();
    log.forEach((e) => {
      events[e.event] = (events[e.event] || 0) + 1;
      sessions.add(e.sessionId);
    });
    const previewStarts = events["preview_started"] || 0;
    const practiceAttempts = events["practice_attempted"] || 0;
    const assessments = log.filter((e) => e.event === "assessment" && e.data);
    const recognizeYes = assessments.filter(
      (e) => e.data.recognize === "yes"
    ).length;
    const avg = (key) =>
      assessments.length
        ? (
            assessments.reduce((s, e) => s + (Number(e.data[key]) || 0), 0) /
            assessments.length
          ).toFixed(1)
        : "—";
    return {
      total: log.length,
      sessions: sessions.size,
      previewStarts,
      practiceAttempts,
      attemptRate:
        previewStarts > 0
          ? Math.round((practiceAttempts / previewStarts) * 100)
          : 0,
      assessments: assessments.length,
      recognizeRate:
        assessments.length > 0
          ? Math.round((recognizeYes / assessments.length) * 100)
          : 0,
      groundedAvg: avg("grounded"),
      intentAvg: avg("intent"),
    };
  }, [log]);

  return (
    <div className={styles.layout}>
      <header className={styles.topbar}>
        <div className={styles.brand}>
          <span className={styles.brandDot} />
          DraWe
        </div>
        <nav className={styles.modeTabs}>
          {[
            { key: "edit", label: "편집" },
            { key: "preview", label: "미리보기" },
            { key: "log", label: "로그" },
          ].map((m) => (
            <button
              key={m.key}
              type="button"
              className={`${styles.modeTab} ${
                mode === m.key ? styles.modeTabActive : ""
              }`}
              onClick={() => handleModeSwitch(m.key)}
            >
              {m.label}
            </button>
          ))}
        </nav>
      </header>

      <main className={styles.main}>
        {/* ===== EDIT MODE ===== */}
        {mode === "edit" && (
          <div className={styles.container}>
            <div className={styles.helpTip}>
              <strong>이렇게 쓰세요</strong> — 사용자 그림을 본 뒤 WoZ 데이터셋에서 가까운 시나리오를 골라 아래 4개 칸을 채우고, <strong>미리보기</strong> 탭을 사용자에게 보여주세요. 사용자 인터랙션이 자동으로 <strong>로그</strong>에 쌓입니다.
            </div>

            <Section title="세션 정보">
              <Field label="세션 ID (사용자 식별용)">
                <input
                  type="text"
                  value={form.sessionId}
                  onChange={(e) => updateForm("sessionId", e.target.value)}
                  placeholder="예: user_지훈_241105"
                />
              </Field>
              <Field label="그림 묘사 / 사용자 메시지 (선택)">
                <input
                  type="text"
                  value={form.userMessage}
                  onChange={(e) => updateForm("userMessage", e.target.value)}
                  placeholder='예: "손이 이상해요"'
                />
              </Field>
            </Section>

            <Section title="샘플 시나리오 불러오기">
              <div className={styles.scenarioPicker}>
                {Object.entries(SCENARIOS).map(([key, s]) => (
                  <button
                    key={key}
                    type="button"
                    className={styles.scenarioBtn}
                    onClick={() => loadScenario(key)}
                  >
                    {s.label}
                  </button>
                ))}
                <button
                  type="button"
                  className={`${styles.scenarioBtn} ${styles.scenarioBtnClear}`}
                  onClick={() => loadScenario("clear")}
                >
                  비우기
                </button>
              </div>
            </Section>

            <Section title="1. 관찰 (이 그림에서 보이는 것)">
              <textarea
                rows={3}
                value={form.card1}
                onChange={(e) => updateForm("card1", e.target.value)}
                placeholder="이 그림에서 구체적으로 어떤 점이 보이는가 — 중립 서술로"
              />
            </Section>

            <Section title="2. 읽히는 느낌 (그것이 만드는 시각적 인상)">
              <textarea
                rows={3}
                value={form.card2}
                onChange={(e) => updateForm("card2", e.target.value)}
                placeholder="관찰된 점이 어떤 시각적 효과를 만드는가 — 판단 아닌 서술로"
              />
            </Section>

            <Section title="3. 이번에 딱 하나 (다음 연습)">
              <textarea
                rows={4}
                value={form.card3}
                onChange={(e) => updateForm("card3", e.target.value)}
                placeholder="다음에 시도해볼 단 하나의 연습"
              />
            </Section>

            <Section title="4. 레퍼런스">
              <Field label="왜 이 레퍼런스가 적합한가">
                <textarea
                  rows={2}
                  value={form.card4Why}
                  onChange={(e) => updateForm("card4Why", e.target.value)}
                  placeholder="이 레퍼런스들이 위 문제에 왜 적합한지"
                />
              </Field>
              <Field label="이미지 URL 1">
                <input
                  type="text"
                  value={form.ref1Url}
                  onChange={(e) => updateForm("ref1Url", e.target.value)}
                  placeholder="https://..."
                />
              </Field>
              <Field label="이미지 URL 2">
                <input
                  type="text"
                  value={form.ref2Url}
                  onChange={(e) => updateForm("ref2Url", e.target.value)}
                  placeholder="https://..."
                />
              </Field>
              <Field label="이미지 URL 3">
                <input
                  type="text"
                  value={form.ref3Url}
                  onChange={(e) => updateForm("ref3Url", e.target.value)}
                  placeholder="https://..."
                />
              </Field>
            </Section>

            <div className={styles.actions}>
              <button
                type="button"
                className={styles.primaryBtn}
                onClick={handleStartPreview}
              >
                사용자에게 보여주기 →
              </button>
              <button
                type="button"
                className={styles.secondaryBtn}
                onClick={newSession}
              >
                새 세션
              </button>
            </div>
          </div>
        )}

        {/* ===== PREVIEW MODE ===== */}
        {mode === "preview" && (
          <div className={styles.containerNarrow}>
            <GuideMessage
              observation={form.card1}
              effect={form.card2}
              practice={form.card3}
              referenceWhy={form.card4Why}
              references={references}
              userMessage={form.userMessage}
              onPracticeAttempted={() => logEvent("practice_attempted")}
              onPracticeDeferred={() => logEvent("practice_deferred")}
              onRefClicked={(idx) => logEvent("reference_clicked", { ref: idx })}
              onRefPinned={(idx, _ref, isPinned) =>
                logEvent(isPinned ? "reference_pinned" : "reference_unpinned", {
                  ref: idx,
                })
              }
              onRefFeedback={(type) =>
                logEvent("reference_feedback", { type })
              }
            />

            {assessment.submitted ? (
              <div className={styles.assessDone}>
                응답이 기록됐어요. 함께 봐줘서 고마워요.
              </div>
            ) : (
              <div className={styles.assess}>
                <div className={styles.assessTitle}>잠깐, 세 가지만</div>
                <AssessRow
                  q="이 코칭이 '무엇을 보라'는 건지 이해됐나요?"
                  options={[
                    ["yes", "예"],
                    ["partly", "부분적"],
                    ["no", "아니오"],
                  ]}
                  value={assessment.recognize}
                  onSelect={(v) => setAssess("recognize", v)}
                />
                <AssessScale
                  q="왜 그런지(근거)가 그림에서 보였나요?"
                  hint="1 전혀 — 5 분명히"
                  value={assessment.grounded}
                  onSelect={(v) => setAssess("grounded", v)}
                />
                <AssessScale
                  q="다음 그림에서 이걸 시도해볼 의향이 있나요?"
                  hint="1 없음 — 5 꼭"
                  value={assessment.intent}
                  onSelect={(v) => setAssess("intent", v)}
                />
                <button
                  type="button"
                  className={styles.primaryBtn}
                  onClick={submitAssessment}
                >
                  응답 보내기
                </button>
              </div>
            )}
          </div>
        )}

        {/* ===== LOG MODE ===== */}
        {mode === "log" && (
          <div className={styles.container}>
            <div className={styles.statGrid}>
              <StatCard label="전체 이벤트" value={stats.total} />
              <StatCard label="고유 세션" value={stats.sessions} />
              <StatCard label="미리보기 노출" value={stats.previewStarts} />
              <StatCard
                label="연습 시도"
                value={`${stats.practiceAttempts}`}
                suffix={`(${stats.attemptRate}%)`}
              />
              <StatCard
                label="인지율 (예)"
                value={`${stats.recognizeRate}%`}
                suffix={`n=${stats.assessments}`}
              />
              <StatCard label="근거 가시성 (평균)" value={stats.groundedAvg} suffix="/5" />
              <StatCard label="시도 의향 (평균)" value={stats.intentAvg} suffix="/5" />
            </div>

            <div className={styles.logActions}>
              <button
                type="button"
                className={styles.logActionBtn}
                onClick={exportLog}
              >
                📥 JSON 내보내기
              </button>
              <button
                type="button"
                className={`${styles.logActionBtn} ${styles.logActionDanger}`}
                onClick={clearLog}
              >
                🗑 모두 지우기
              </button>
            </div>

            <div className={styles.logDisplay}>
              {log.length === 0 ? (
                <div className={styles.logEmpty}>로그가 비어 있어요.</div>
              ) : (
                log
                  .slice()
                  .reverse()
                  .map((e, i) => {
                    const time = new Date(e.timestamp).toLocaleString("ko-KR");
                    const dataStr = e.data ? JSON.stringify(e.data) : "";
                    const dwell =
                      e.secondsSincePreview != null
                        ? ` · ${e.secondsSincePreview}s`
                        : "";
                    return (
                      <div key={i} className={styles.logEntry}>
                        <span className={styles.logTime}>{time}</span>
                        <span className={styles.logEvent}>{e.event}</span>
                        <span className={styles.logData}>
                          [{e.sessionId}]{dwell} {dataStr}
                        </span>
                      </div>
                    );
                  })
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

const Section = ({ title, children }) => (
  <section className={styles.editSection}>
    <h2 className={styles.editSectionTitle}>{title}</h2>
    {children}
  </section>
);

const Field = ({ label, children }) => (
  <div className={styles.field}>
    <label className={styles.fieldLabel}>{label}</label>
    {children}
  </div>
);

const StatCard = ({ label, value, suffix }) => (
  <div className={styles.statCard}>
    <div className={styles.statLabel}>{label}</div>
    <div className={styles.statValue}>
      {value}
      {suffix && <span className={styles.statSuffix}> {suffix}</span>}
    </div>
  </div>
);

const AssessRow = ({ q, options, value, onSelect }) => (
  <div className={styles.assessRow}>
    <div className={styles.assessQ}>{q}</div>
    <div className={styles.assessOpts}>
      {options.map(([val, label]) => (
        <button
          key={val}
          type="button"
          className={`${styles.assessOpt} ${
            value === val ? styles.assessOptActive : ""
          }`}
          onClick={() => onSelect(val)}
        >
          {label}
        </button>
      ))}
    </div>
  </div>
);

const AssessScale = ({ q, hint, value, onSelect }) => (
  <div className={styles.assessRow}>
    <div className={styles.assessQ}>{q}</div>
    <div className={styles.assessOpts}>
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          className={`${styles.assessOpt} ${styles.assessScaleOpt} ${
            value === n ? styles.assessOptActive : ""
          }`}
          onClick={() => onSelect(n)}
        >
          {n}
        </button>
      ))}
    </div>
    {hint && <div className={styles.assessHint}>{hint}</div>}
  </div>
);

export default WozTestPage;
