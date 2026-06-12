import { useRef, useState } from "react";

/**
 * GuideEntry — FastAPI(artcoach) 단독 테스트용 입구 (목업 디자인 적용).
 *
 * 이 파일 하나만 덮어쓰면 새 5섹션 UI가 뜬다(GuideMessage/NextSteps/Roadmap/GuideAsset 불필요).
 * 흐름: 그림 업로드 + "어떤 점이 마음에 걸리나요?" → POST /guide(multipart)
 *       → GuideResponse(mode=coach…) → 1.분석 / 2.읽히는 느낌 / 3.한 끗 포인트
 *          / 4.추천 레퍼런스 / 5.앞으로 해야 할 것 + 성장 흐름(/roadmap).
 * 레퍼런스: reference_ids → `${API_BASE}/image/{id}` (백엔드 302). 도식: /guide-asset/{ref_id}.
 * 백엔드 주소: VITE_API_BASE 우선, 없으면 localhost:8000 (상단 입력으로 덮어쓰기 가능).
 */
const API_DEFAULT =
  (typeof import.meta !== "undefined" &&
    import.meta.env &&
    import.meta.env.VITE_API_BASE) ||
  "http://localhost:8000";

// sub_problem → 한글 라벨 (roadmap.py LABELS 와 동일)
const LABELS = {
  weight_balance: "무게중심", foreshortening: "단축(투시)", proportion: "비율",
  action_line: "동세", joint_articulation: "관절", hand_structure: "손 구조",
  value_structure: "명암", composition_balance: "구도", color_harmony: "색 조화",
  light_direction: "빛 방향", linear_perspective: "선원근",
  atmospheric_perspective: "대기원근", depth_layering: "공간 깊이", horizon_placement: "지평선 배치",
};
const L = (sp) => LABELS[sp] || sp;

// 빠른 칩 — 클릭하면 message 에 라벨이 더해진다(라우터가 키워드로 taxonomy 항목을 surface).
const CHIPS = ["손이 어색해요", "얼굴이 어색해요", "입체감이 없어요", "구도가 단조로워요", "톤을 바꾸고 싶어요"];

export default function GuideEntry() {
  const [apiBase, setApiBase] = useState(API_DEFAULT);
  const [userId, setUserId] = useState("test_user");
  const [file, setFile] = useState(null);
  const [message, setMessage] = useState("");
  const [chipSel, setChipSel] = useState([]);
  const [intent, setIntent] = useState("open");   // 작업중=open / 완성작=finished
  const [style, setStyle] = useState("");          // ""=자동, "sketch"=스케치(medium)
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [resultImg, setResultImg] = useState(null);
  const [growth, setGrowth] = useState(null);
  const [error, setError] = useState(null);
  const fileRef = useRef(null);

  const api = () => apiBase.replace(/\/+$/, "");
  const uid = () => userId.trim() || "test_user";

  function pickFile(f) {
    setFile(f || null);
  }
  function toggleChip(c) {
    if (chipSel.includes(c)) {
      setChipSel(chipSel.filter((x) => x !== c));
      setMessage((m) => m.replace(c, "").replace(/\s+/g, " ").trim());
    } else {
      setChipSel([...chipSel, c]);
      setMessage((m) => (m ? m + " " : "") + c);
    }
  }

  async function submit() {
    if (!file) return;
    setLoading(true); setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("message", message);
      fd.append("user_id", uid());
      fd.append("intent", intent);
      if (style) fd.append("medium", style);     // '스케치' → medium 소프트 부스트
      const res = await fetch(api() + "/guide", { method: "POST", body: fd });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      setResult(data);
      setResultImg(URL.createObjectURL(file));
      loadGrowth();
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  async function loadGrowth() {
    try {
      const res = await fetch(`${api()}/roadmap?user_id=${encodeURIComponent(uid())}`);
      setGrowth(await res.json());
    } catch (e) {
      setGrowth({ __error: e.message });
    }
  }

  function reset() {
    setResult(null); setResultImg(null); setGrowth(null); setError(null);
  }

  return (
    <div className="gt-app">
      <style>{CSS}</style>

      <nav className="gt-rail">
        <div className="gt-dot off">S</div>
        <div className="gt-dot on">📁</div>
        <div className="gt-dot off">🗄</div>
      </nav>

      <div className="gt-main">
        <div className="gt-topbar">
          <div className="gt-title">
            {result && result.primary_focus ? `${L(result.primary_focus)} 한 끗 가이드` : "한 끗 가이드 · FastAPI 테스트"}
          </div>
          <div className="gt-settings">
            <label>API</label>
            <input value={apiBase} size={22} placeholder="http://localhost:8000"
                   onChange={(e) => setApiBase(e.target.value)} />
            <label>user_id</label>
            <input value={userId} size={12} onChange={(e) => setUserId(e.target.value)} />
          </div>
        </div>

        <div className="gt-col">
          {error && (
            <div className="gt-banner err">
              요청 실패: {error}
              <br />
              {String(error).includes("Failed to fetch")
                ? "FastAPI(8000)가 떠 있는지, CORS_ORIGINS 에 이 주소가 있는지 확인하세요."
                : "응답을 처리하지 못했습니다."}
            </div>
          )}

          {!result ? (
            <Form
              file={file} fileRef={fileRef} onPick={pickFile}
              message={message} setMessage={setMessage}
              chipSel={chipSel} toggleChip={toggleChip}
              style={style} setStyle={setStyle}
              intent={intent} setIntent={setIntent}
              loading={loading} onSubmit={submit}
            />
          ) : result.mode !== "coach" ? (
            <>
              <div className="gt-banner">{result.message || "코칭 대상이 아니에요."}</div>
              <button className="gt-back" onClick={reset}>← 다른 그림 보기</button>
            </>
          ) : (
            <Result data={result} img={resultImg} api={api()} growth={growth} onBack={reset} />
          )}
        </div>
      </div>
    </div>
  );
}

/* ── 입력 폼 (이미지 3) ─────────────────────────────────────────── */
function Form({ file, fileRef, onPick, message, setMessage, chipSel, toggleChip,
                style, setStyle, intent, setIntent, loading, onSubmit }) {
  return (
    <div className="gt-form">
      <h2>한 끗 가이드</h2>

      <div className="gt-flabel">그림 업로드</div>
      {!file ? (
        <div className="gt-drop"
             onClick={(e) => { if (e.target.classList.contains("gt-drop")) fileRef.current.click(); }}
             onDragOver={(e) => e.preventDefault()}
             onDrop={(e) => { e.preventDefault(); if (e.dataTransfer.files[0]) onPick(e.dataTransfer.files[0]); }}>
          첨부할 파일 한 장을 여기에 끌어다 놓거나, 직접 선택해주세요.
          <div>
            <button className="gt-pick" type="button" onClick={() => fileRef.current.click()}>⬆ 파일 선택</button>
          </div>
        </div>
      ) : (
        <div className="gt-filepreview">
          <div className="gt-fthumb"><img src={URL.createObjectURL(file)} alt="" /></div>
          <div>
            <div className="gt-fname">{file.name}</div>
            <div className="gt-fsize">{(file.size / 1024 / 1024).toFixed(1)}MB</div>
          </div>
          <button className="gt-x" type="button" onClick={() => onPick(null)}>×</button>
        </div>
      )}
      <input ref={fileRef} type="file" accept="image/*" style={{ display: "none" }}
             onChange={(e) => e.target.files[0] && onPick(e.target.files[0])} />

      <div className="gt-flabel">어떤 점이 마음에 걸리시나요?</div>
      <input className="gt-ti" value={message} onChange={(e) => setMessage(e.target.value)}
             placeholder="예: 얼굴 부분의 명암 단계가 다 비슷해 보여서 평평하게 읽혀요" />
      <div className="gt-chips">
        {CHIPS.map((c) => (
          <button key={c} type="button"
                  className={chipSel.includes(c) ? "sel" : ""}
                  onClick={() => toggleChip(c)}>{c}</button>
        ))}
      </div>

      <div className="gt-flabel">이 그림 화풍은</div>
      <select className="gt-ti" value={style} onChange={(e) => setStyle(e.target.value)}>
        <option value="">자동 (AI 자동 판단)</option>
        <option value="sketch">스케치</option>
      </select>

      <div className="gt-flabel">이 그림의 상태는</div>
      <div className="gt-toggle">
        <button type="button" className={intent === "open" ? "sel" : ""} onClick={() => setIntent("open")}>작업중</button>
        <button type="button" className={intent === "finished" ? "sel" : ""} onClick={() => setIntent("finished")}>완성작</button>
      </div>

      <button className="gt-submit" type="button" disabled={!file || loading} onClick={onSubmit}>
        {loading ? <><span className="gt-spinner" /> 분석 중…</> : "가이드 요청하기"}
      </button>
    </div>
  );
}

/* ── 결과 (이미지 1·2) ──────────────────────────────────────────── */
function Result({ data, img, api, growth, onBack }) {
  const b = (data.blocks && data.blocks[0]) || {};
  const ns = data.next_steps || {};
  const goalSp = ns.next_goal || ns.focus;
  const goalPractice = ns.next_goal_practice || ns.focus_practice || data.one_thing || "";
  const refs = (b.reference_ids || []).slice(0, 3);
  const [reactions, setReactions] = useState({});   // ref_id -> "like" | "dislike" | null

  async function react(refId, kind) {
    const next = reactions[refId] === kind ? null : kind;   // 같은 버튼 다시 누르면 취소(토글)
    setReactions((r) => ({ ...r, [refId]: next }));
    if (!next) return;                                       // 취소면 로깅 안 함
    try {
      await fetch(api + "/adopt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          guide_id: data.guide_id || "",                     // 노출(shown) 로그와 join → sub_problem 회수
          reference_id: refId,
          persona: "", source_type: "",
          event: kind === "like" ? "liked" : "disliked",     // 검색 랭킹에 ±가중 반영
        }),
      });
    } catch (e) { /* 피드백 로깅 실패가 화면을 막지 않게 무시 */ }
  }

  return (
    <>
      <Section n="1. 분석">
        <div className="gt-card gt-analysis">
          <div className="gt-thumb">{img && <img src={img} alt="업로드 그림" />}</div>
          <div className="gt-lead">{b.observation || "관찰 내용이 여기 표시됩니다."}</div>
        </div>
      </Section>

      <Section n="2. 읽히는 느낌">
        <div className="gt-card"><div className="gt-lead">{b.effect || "읽히는 느낌이 여기 표시됩니다."}</div></div>
      </Section>

      <Section n="3. 한 끗 포인트" accent>
        <div className="gt-card accent">
          <div className="gt-lead">{b.direction || data.one_thing || "지금 해볼 실험이 여기 표시됩니다."}</div>
          {b.guide_asset && b.guide_asset.ref_id && (
            <div className="gt-asset">
              <img src={`${api}/guide-asset/${b.guide_asset.ref_id}`} alt={b.guide_asset.label || ""}
                   onError={(e) => (e.currentTarget.style.display = "none")} />
              {b.guide_asset.caption && <div className="gt-cap">{b.guide_asset.caption}</div>}
            </div>
          )}
        </div>
      </Section>

      <Section n="4. 추천 레퍼런스">
        <div className="gt-card">
          <div className="gt-refs">
            {refs.length ? refs.map((id, i) => (
              <div className="gt-refcard" key={id}>
                <div className="gt-ph"><img src={`${api}/image/${id}`} alt=""
                  onError={(e) => { e.currentTarget.parentNode.textContent = "🖼"; }} /></div>
                <div className="gt-meta">
                  <span className="gt-n">{i + 1}</span>
                  <span className="gt-labl">레퍼런스</span>
                  <span className="gt-cardreact">
                    <button className={reactions[id] === "like" ? "on" : ""}
                            onClick={() => react(id, "like")} title="도움돼요">👍</button>
                    <button className={reactions[id] === "dislike" ? "on" : ""}
                            onClick={() => react(id, "dislike")} title="별로예요">👎</button>
                  </span>
                </div>
              </div>
            )) : <div className="gt-muted" style={{ gridColumn: "1/-1", padding: 8 }}>레퍼런스가 아직 없어요(코퍼스 보강 대상).</div>}
          </div>
        </div>
      </Section>

      <Section n="5. 앞으로 해야 할 것">
        <div className="gt-card">
          {goalSp ? (
            <>
              <div className="gt-goal"><span className="gt-chip">다음 목표</span><span className="gt-name">{L(goalSp)}</span></div>
              <div className="gt-lead">{goalPractice}</div>
            </>
          ) : <div className="gt-lead gt-muted">아직 다음 목표가 정해지지 않았어요.</div>}
        </div>
      </Section>

      <Section n="성장 흐름" accent>
        <Growth growth={growth} />
      </Section>

      <button className="gt-back" onClick={onBack}>← 다른 그림 보기</button>
    </>
  );
}

function Section({ n, accent, children }) {
  return (
    <div className="gt-sec">
      <span className={"gt-sec-label" + (accent ? " accent" : "")}>{n}</span>
      {children}
    </div>
  );
}

/* ── 성장 흐름 (/roadmap) ──────────────────────────────────────── */
function Growth({ growth }) {
  if (!growth) return <div className="gt-lead gt-muted">성장 흐름 불러오는 중…</div>;
  if (growth.__error) return <div className="gt-lead gt-muted">성장 흐름을 불러오지 못했어요 ({growth.__error}).</div>;

  const tl = (growth.timeline || []).map((t) => t.flagged_count ?? 0);
  const current = growth.current && growth.current.sub_problem ? [L(growth.current.sub_problem)] : [];
  const banner = growth.goal ? <GoalBanner goal={growth.goal} /> : null;

  if (tl.length < 3) {
    return (
      <>
        {banner}
        <div className="gt-cream">
          <div className="gt-cold">처음으로 한 끗 가이드를 사용하셨어요!<br />
            몇 번 더 사용하면 지금까지 어떤 어려움을 가장 많이 겪는지 보여드릴게요.</div>
        </div>
        <StageRow k="현재 그림 단계" tags={current} />
      </>
    );
  }

  const first = tl[0] || 0, last = tl[tl.length - 1] || 0;
  const pct = first > 0 ? Math.round(((first - last) / first) * 100) : 0;
  const steady = (growth.ladder || []).filter((x) => x.status === "steady").map((x) => L(x.sub_problem)).slice(0, 3);

  return (
    <>
      {banner}
      <div className="gt-cream">
        <div className="gt-chartbox">
          <div className="gt-chart-title">그림 한 장당 어려움을 느낀 횟수</div>
          <Sparkline vals={tl} />
        </div>
        <div className="gt-note">처음 가이드를 요청했을 때보다 어려움을 보이는 부분이{" "}
          <b>{pct >= 0 ? `${pct}% 감소` : `${Math.abs(pct)}% 증가`}</b>했어요!</div>
      </div>
      <StageRow k="현재 그림 단계" tags={current} />
      {steady.length > 0 && <StageRow k="최근에 덜 보이는 어려움" tags={steady} />}
    </>
  );
}

/* 이번 목표(N장 기준 고정) — 진행/달성 진급 표시 */
function GoalBanner({ goal }) {
  return (
    <div className="gt-goalbox">
      {goal.just_achieved && goal.prev_achieved && (
        <div className="gt-celebrate">🎉 {L(goal.prev_achieved)} 달성 — 다음 목표로 넘어가요</div>
      )}
      <div className="gt-goalrow">
        <span className="gt-chip">이번 목표</span>
        <span className="gt-name">{L(goal.sub_problem)}</span>
        <span className="gt-goalprog">고정 후 {goal.uploads_since}장 · 처음 {goal.baseline_count}회 → 지금 {goal.current_count}회</span>
      </div>
    </div>
  );
}

function StageRow({ k, tags }) {
  const list = tags.length ? tags : ["—"];
  return (
    <div className="gt-stagebox">
      <span className="gt-k">{k}</span>
      {list.map((t, i) => <span className="gt-tag" key={i}>{t}</span>)}
    </div>
  );
}

function Sparkline({ vals }) {
  const w = 360, h = 90, pad = 4;
  const max = Math.max(...vals, 1), n = vals.length;
  const x = (i) => pad + (i * (w - 2 * pad)) / Math.max(n - 1, 1);
  const y = (v) => pad + (h - 2 * pad) * (1 - v / max);
  const pts = vals.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`);
  const area = `M${pad},${h} L` + pts.join(" L") + ` L${w - pad},${h} Z`;
  const line = "M" + pts.join(" L");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height="100" preserveAspectRatio="none" style={{ marginTop: 8 }}>
      <defs>
        <linearGradient id="gtg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#FF8534" stopOpacity="0.55" />
          <stop offset="100%" stopColor="#FF8534" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill="url(#gtg)" />
      <path d={line} fill="none" stroke="#FF8534" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

/* ── 스타일 (Figma 토큰, .gt-app 하위로 스코프) ───────────────────── */
const CSS = `
.gt-app{--orange:#FF8534;--orange-soft:#FFFBF5;--orange-chip:#FFF1DC;--ink:#24221F;--body:#4A4846;
  --muted:#888685;--line:#EDEBEA;--line2:#D8D7D5;--bg:#FEFEFF;--rail:#FBFBFB;--img:#F6F6F6;
  display:flex;min-height:100vh;background:var(--bg);color:var(--body);
  font-family:'Wanted Sans Variable','Pretendard',system-ui,-apple-system,'Apple SD Gothic Neo',sans-serif;-webkit-font-smoothing:antialiased}
.gt-app *{box-sizing:border-box}
.gt-rail{width:72px;flex:none;background:var(--rail);border-right:1px solid var(--line);display:flex;flex-direction:column;align-items:center;gap:14px;padding:20px 0}
.gt-dot{width:40px;height:40px;border-radius:12px;display:grid;place-items:center;color:#fff;font-weight:700}
.gt-dot.on{background:var(--orange)} .gt-dot.off{background:#EFEDEA;color:var(--muted)}
.gt-main{flex:1;display:flex;flex-direction:column;min-width:0}
.gt-topbar{display:flex;align-items:center;gap:16px;padding:24px 32px 8px}
.gt-title{font-weight:700;font-size:24px;line-height:32px;color:#0F0F0F}
.gt-settings{margin-left:auto;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.gt-settings input{border:1px solid var(--line);border-radius:8px;padding:6px 10px;font-size:13px;color:var(--body);background:#fff}
.gt-settings label{font-size:12px;color:var(--muted)}
.gt-col{width:100%;max-width:836px;margin:0 auto;padding:12px 48px 64px}
.gt-sec{margin-top:40px}
.gt-sec-label{display:inline-block;font-weight:700;font-size:18px;line-height:24px;color:var(--ink);margin-bottom:8px}
.gt-sec-label.accent{color:var(--orange)}
.gt-card{border:1px solid var(--line);border-radius:12px;background:#fff;padding:24px}
.gt-card.accent{background:var(--orange-soft);border-color:var(--orange)}
.gt-lead{font-size:14px;line-height:22px;color:var(--body)}
.gt-muted{color:var(--muted)}
.gt-analysis{display:flex;flex-direction:column;gap:16px}
.gt-thumb{width:170px;height:170px;border-radius:8px;background:var(--img);border:1px solid var(--line);overflow:hidden;display:grid;place-items:center}
.gt-thumb img{width:100%;height:100%;object-fit:cover}
.gt-asset{margin-top:16px;background:#fff;border:1px solid var(--line);border-radius:8px;padding:16px;display:flex;flex-direction:column;align-items:center;gap:8px;max-width:360px}
.gt-asset img{max-width:100%;height:auto;border-radius:6px}
.gt-cap{font-size:12px;line-height:18px;color:var(--muted);text-align:center}
.gt-refs{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.gt-ph{aspect-ratio:1/1;background:var(--img);border-radius:8px;box-shadow:0 2px 15px rgba(15,15,15,.05);overflow:hidden;display:grid;place-items:center;color:var(--line2)}
.gt-ph img{width:100%;height:100%;object-fit:cover}
.gt-meta{display:flex;align-items:center;gap:8px;padding:8px 0 0 4px}
.gt-n{background:var(--img);border-radius:4px;padding:0 8px;font-size:12px;color:var(--body);line-height:20px}
.gt-labl{font-size:14px;font-weight:600;color:var(--ink)}
.gt-cardreact{display:inline-flex;gap:2px;margin-left:auto}
.gt-cardreact button{border:none;background:transparent;border-radius:6px;cursor:pointer;font-size:14px;line-height:1;padding:3px 5px;opacity:.5}
.gt-cardreact button:hover{background:var(--img);opacity:1}
.gt-cardreact button.on{opacity:1;background:var(--orange-chip)}
.gt-reactions{display:flex;gap:6px;margin-top:12px}
.gt-reactions button{width:28px;height:28px;border:none;background:transparent;border-radius:8px;cursor:pointer;color:var(--body);font-size:15px}
.gt-reactions button:hover{background:var(--img)}
.gt-goal{display:flex;align-items:center;gap:12px;margin-bottom:12px}
.gt-chip{background:var(--orange-chip);color:var(--orange);font-weight:600;font-size:14px;border-radius:999px;padding:8px 12px}
.gt-name{font-weight:700;font-size:18px;color:var(--body)}
.gt-goalbox{border:1px solid var(--orange);background:var(--orange-soft);border-radius:12px;padding:16px 20px;margin-bottom:8px}
.gt-celebrate{font-size:14px;font-weight:700;color:var(--orange);margin-bottom:8px}
.gt-goalrow{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.gt-goalprog{font-size:12px;color:var(--muted)}
.gt-cream{background:var(--orange-chip);border-radius:12px;padding:24px}
.gt-chartbox{background:#fff;border-radius:8px;padding:24px}
.gt-chart-title{font-size:14px;font-weight:600;color:var(--muted)}
.gt-cold{font-size:13px;line-height:22px;color:var(--body)}
.gt-note{font-size:12px;line-height:20px;color:var(--body);margin-top:12px}
.gt-note b{color:var(--orange)}
.gt-stagebox{display:flex;align-items:center;gap:12px;border:1px solid var(--line);border-radius:12px;padding:16px 24px;margin-top:8px}
.gt-k{font-size:14px;color:var(--muted)}
.gt-tag{border:1px solid var(--line);border-radius:8px;padding:8px 16px;font-size:16px;color:var(--body);background:#fff}
.gt-form{border:1px solid var(--line);border-radius:16px;background:#fff;padding:28px;margin-top:8px;max-width:680px;margin-left:auto;margin-right:auto}
.gt-form h2{margin:0 0 4px;font-size:20px;font-weight:700;color:var(--ink)}
.gt-flabel{font-size:13px;color:var(--body);margin:18px 0 8px;font-weight:600}
.gt-drop{border:1px dashed var(--orange);background:var(--orange-soft);border-radius:12px;padding:24px;text-align:center;color:var(--muted);font-size:13px;cursor:pointer}
.gt-pick{margin-top:12px;display:inline-flex;gap:6px;align-items:center;background:var(--orange);color:#fff;border:none;border-radius:8px;padding:10px 16px;font-size:14px;font-weight:600;cursor:pointer}
.gt-filepreview{display:flex;align-items:center;gap:12px;border:1px solid var(--line);border-radius:12px;padding:12px}
.gt-fthumb{width:56px;height:56px;border-radius:8px;background:var(--img);overflow:hidden;display:grid;place-items:center}
.gt-fthumb img{width:100%;height:100%;object-fit:cover}
.gt-fname{font-weight:600;color:var(--ink);font-size:14px} .gt-fsize{font-size:12px;color:var(--muted)}
.gt-x{margin-left:auto;border:none;background:transparent;font-size:18px;color:var(--muted);cursor:pointer}
.gt-ti{width:100%;border:1px solid var(--line);border-radius:8px;padding:12px 14px;font-size:14px;color:var(--body);background:#fff}
.gt-chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.gt-chips button{border:1px solid var(--line);background:#fff;border-radius:999px;padding:8px 14px;font-size:13px;color:var(--body);cursor:pointer}
.gt-chips button.sel{border-color:var(--orange);color:var(--orange);background:var(--orange-soft)}
.gt-toggle{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden}
.gt-toggle button{border:none;background:#fff;padding:8px 16px;font-size:14px;color:var(--body);cursor:pointer}
.gt-toggle button.sel{background:var(--orange);color:#fff;font-weight:600}
.gt-submit{margin-top:24px;width:100%;border:none;border-radius:10px;padding:14px;font-size:15px;font-weight:700;color:#fff;background:var(--orange);cursor:pointer}
.gt-submit:disabled{background:#E7E4E0;color:#B6B2AD;cursor:not-allowed}
.gt-banner{width:100%;padding:10px 14px;margin-bottom:16px;border:1px solid var(--line);border-radius:12px;background:var(--orange-soft);font-size:13px;color:var(--body)}
.gt-banner.err{background:#FEECEC;border-color:#F5B5B5;color:#9B2C2C}
.gt-spinner{display:inline-block;width:14px;height:14px;border:2px solid var(--line2);border-top-color:var(--orange);border-radius:50%;animation:gtspin .8s linear infinite;vertical-align:middle}
@keyframes gtspin{to{transform:rotate(360deg)}}
.gt-back{border:1px solid var(--line);background:#fff;border-radius:8px;padding:8px 14px;font-size:13px;color:var(--body);cursor:pointer;margin-top:24px}
`;
