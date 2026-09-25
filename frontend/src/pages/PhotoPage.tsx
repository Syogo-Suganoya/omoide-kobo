import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { api } from "../api";
import { Confidence, ErrorBar, StatusChip } from "../components/bits";
import { NowBar } from "../components/nowbar";
import type { Photo } from "../types";

export default function PhotoPage() {
  const { photoId = "" } = useParams();
  const [photo, setPhoto] = useState<Photo | null>(null);
  const [siblings, setSiblings] = useState<Photo[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [place, setPlace] = useState("");
  const [era, setEra] = useState("");
  const [correction, setCorrection] = useState("");
  const [who, setWho] = useState("母");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async () => {
    const p = await api.getPhoto(photoId);
    setPhoto(p);
    setSiblings(await api.listPhotos(p.album_id));
    setPlace(p.confirmed.place ?? "");
    // 場所と同じく、AI の推定は初期値に入れない。
    // 触っていない欄がそのまま「家族が確定した記憶」になってしまうため。
    setEra(p.confirmed.era ?? "");
    setCorrection(p.confirmed.family_correction ?? "");
  }, [photoId]);

  useEffect(() => {
    load().catch(setError);
  }, [load]);

  const run = async (key: string, fn: () => Promise<unknown>) => {
    setBusy(key);
    setError(null);
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  };

  const confirmRef = useRef<HTMLDetailsElement>(null);

  const jump = () => {
    const el = confirmRef.current;
    if (el) el.open = true;
    el?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  if (!photo) return <ErrorBar error={error ?? null} />;

  const top = photo.estimate?.place_candidates[0];
  const topEra = photo.estimate?.era;

  const at = siblings.findIndex((p) => p.id === photo.id);
  const neighbours = { prev: siblings[at - 1], next: siblings[at + 1] };

  return (
    <>
      <ErrorBar error={error} />
      <NowBar photo={photo} neighbours={neighbours} onJump={jump} />

      <div className="split">
        <div className="stack">
          <section className="card">
            <div className="row" style={{ justifyContent: "space-between", marginBottom: 10 }}>
              <h2 style={{ marginBottom: 0 }}>{photo.confirmed.place ?? photo.filename}</h2>
              <StatusChip status={photo.status} />
            </div>
            <img
              className="photo"
              src={api.imageUrl(photo.id)}
              alt={photo.confirmed.place ?? photo.filename}
            />
          </section>

          {photo.estimate && (
            <section className="card">
              <h3>AI の推定（候補です）</h3>
              <p className="lead" style={{ marginBottom: 12 }}>
                推定は根拠と確度つきの候補です。家族の記憶が違えば、そちらが正しい記録になります。
              </p>

              {photo.estimate.place_candidates.map((cand, i) => (
                <div key={cand.name} className={`candidate ${i === 0 ? "" : "secondary"}`}>
                  <div className="row" style={{ justifyContent: "space-between" }}>
                    <b>{cand.name}</b>
                    <button
                      className="btn small ghost"
                      onClick={() => setPlace(cand.name)}
                      type="button"
                    >
                      これを候補に入れる
                    </button>
                  </div>
                  {cand.address && (
                    <p style={{ color: "var(--sub)", fontSize: "0.8rem" }}>{cand.address}</p>
                  )}
                  <Confidence value={cand.confidence} />
                  <ul className="evidence">
                    {cand.evidence.map((ev) => (
                      <li key={ev}>{ev}</li>
                    ))}
                  </ul>
                </div>
              ))}

              {photo.estimate.era && (
                <div className="candidate secondary">
                  <b>年代: {photo.estimate.era.label}</b>
                  <Confidence value={photo.estimate.era.confidence} />
                  <ul className="evidence">
                    {photo.estimate.era.evidence.map((ev) => (
                      <li key={ev}>{ev}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="row" style={{ marginTop: 10 }}>
                {photo.estimate.features.map((f) => (
                  <span key={f} className="chip muted">
                    {f}
                  </span>
                ))}
              </div>
            </section>
          )}
        </div>

        <div className="stack">
          {/* 確定が済んだら畳む。いまやることと、画面の大きさを合わせる */}
          <details className="card fold" ref={confirmRef} open={!photo.confirmed.place}>
            <summary>
              <h3>家族にたずねる</h3>
              <span className={`chip ${photo.confirmed.place ? "muted" : "aka"}`}>
                {photo.confirmed.place ? "確定済み・直せます" : "いまここ"}
              </span>
            </summary>
            <p className="lead">
              推定の決め手を、覚えている人に確かめます。
              {photo.questions.length > 0 && "答えられるものだけで構いません。下の「場所」が入っていれば確定できます。"}
            </p>
            {photo.questions.length === 0 && <div className="empty">質問はまだありません。</div>}
            {photo.questions.map((q, i) => (
              <div className="field" key={q.id}>
                {/* 何を確かめたい質問かを番号と一緒に出す。3つ並ぶので見分けがつくようにする */}
                <span className="label">
                  質問 {i + 1}／{photo.questions.length}・{q.reason}
                </span>
                <p style={{ fontSize: "0.9rem", marginBottom: 6 }}>{q.text}</p>
                <input
                  placeholder={q.answered ? "" : "覚えていれば書く（任意）"}
                  value={answers[q.id] ?? q.answer ?? ""}
                  onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })}
                />
              </div>
            ))}

            <hr style={{ border: 0, borderTop: "1px dashed var(--line)", margin: "14px 0" }} />

            <div className="field">
              <span className="label">場所（家族の記憶が最優先）</span>
              {/* 空欄のまま確定できてしまわないように。AI の候補は入れず、押して入れてもらう */}
              <input
                value={place}
                onChange={(e) => setPlace(e.target.value)}
                placeholder={top ? `例: ${top.name}` : "例: JR只見線 会津柳津駅"}
              />
              {!place && top && (
                <button
                  type="button"
                  className="btn ghost small"
                  style={{ marginTop: 6 }}
                  onClick={() => setPlace(top.name)}
                >
                  「{top.name}」を入れる
                </button>
              )}
            </div>
            <div className="field">
              <span className="label">年代（分からなければ空のままで構いません）</span>
              {/* 場所と同じ扱い。AI の推定は押して入れてもらう */}
              <input
                value={era}
                onChange={(e) => setEra(e.target.value)}
                placeholder={topEra ? `例: ${topEra.label}` : "例: 昭和42年ごろ"}
              />
              {!era && topEra && (
                <button
                  type="button"
                  className="btn ghost small"
                  style={{ marginTop: 6 }}
                  onClick={() => setEra(topEra.label)}
                >
                  「{topEra.label}」を入れる
                </button>
              )}
            </div>
            <div className="field">
              <span className="label">AI の推定への訂正メモ</span>
              <textarea
                rows={2}
                value={correction}
                onChange={(e) => setCorrection(e.target.value)}
                placeholder="例: 只見線ではなく五能線。祖母の実家の最寄り駅"
              />
            </div>
            <div className="field">
              <span className="label">確定した人</span>
              <input value={who} onChange={(e) => setWho(e.target.value)} />
            </div>

            <div className="row" style={{ alignItems: "center" }}>
              <button
                className="btn"
                disabled={busy !== null || !place.trim()}
                onClick={() =>
                  run("confirm", () =>
                    api.confirmPhoto(photo.id, {
                      place: place || undefined,
                      era: era || undefined,
                      family_correction: correction || undefined,
                      confirmed_by: who,
                      answers: Object.entries(answers).map(([question_id, answer]) => ({
                        question_id,
                        answer,
                      })),
                    })
                  )
                }
              >
                家族の記憶として確定する
              </button>
              <button
                className="btn ghost"
                disabled={busy !== null}
                onClick={() => run("reestimate", () => api.reestimate(photo.id))}
              >
                訂正を踏まえて推定し直す
              </button>
              {!place.trim() && (
                <span style={{ color: "var(--aka)", fontSize: "0.82rem" }}>
                  場所を入れると確定できます
                </span>
              )}
            </div>

            {photo.confirmed.confirmed_at && (
              <p className="notice" style={{ marginTop: 12 }}>
                {photo.confirmed.confirmed_by} さんが「{photo.confirmed.place}」として確定しました。
                以後この写真の場所は、AI の候補ではなくこちらが使われます。
              </p>
            )}
          </details>

        </div>
      </div>
    </>
  );
}
