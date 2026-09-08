import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { api } from "../api";
import { BeforeAfter, Confidence, ErrorBar, StatusChip } from "../components/bits";
import { NowBar } from "../components/nowbar";
import type { Photo } from "../types";

function useRecorder(onDone: (blob: Blob) => void) {
  const [recording, setRecording] = useState(false);
  const [supported] = useState(() => typeof MediaRecorder !== "undefined");
  const recorder = useRef<MediaRecorder | null>(null);

  const start = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const chunks: BlobPart[] = [];
    const rec = new MediaRecorder(stream);
    rec.ondataavailable = (e) => chunks.push(e.data);
    rec.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      onDone(new Blob(chunks, { type: "audio/webm" }));
    };
    rec.start();
    recorder.current = rec;
    setRecording(true);
  };

  const stop = () => {
    recorder.current?.stop();
    setRecording(false);
  };

  return { recording, supported, start, stop };
}

export default function PhotoPage() {
  const { photoId = "" } = useParams();
  const [photo, setPhoto] = useState<Photo | null>(null);
  const [siblings, setSiblings] = useState<Photo[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [place, setPlace] = useState("");
  const [era, setEra] = useState("");
  const [correction, setCorrection] = useState("");
  const [who, setWho] = useState("母");
  const [transcript, setTranscript] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async () => {
    const p = await api.getPhoto(photoId);
    setPhoto(p);
    setSiblings(await api.listPhotos(p.album_id));
    setPlace(p.confirmed.place ?? "");
    setEra(p.confirmed.era ?? p.estimate?.era?.label ?? "");
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

  const recorder = useRecorder((blob) =>
    run("story", () => api.addStoryAudio(photoId, blob, who))
  );

  const confirmRef = useRef<HTMLDetailsElement>(null);
  const storyRef = useRef<HTMLDetailsElement>(null);

  const jump = (target: "confirm" | "story") => {
    const el = target === "confirm" ? confirmRef.current : storyRef.current;
    if (el) el.open = true;
    el?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  if (!photo) return <ErrorBar error={error ?? null} />;

  const top = photo.estimate?.place_candidates[0];

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
            {photo.restored_ref ? (
              <BeforeAfter
                before={api.imageUrl(photo.id, "original")}
                after={api.imageUrl(photo.id, "restored")}
              />
            ) : (
              <div className="empty">修復中です…</div>
            )}
            <div className="row" style={{ marginTop: 10 }}>
              {photo.restore_steps.map((step) => (
                <span key={step} className="chip iro">
                  {step}
                </span>
              ))}
            </div>
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
            <p className="lead">推定の決め手を、覚えている人に確かめます。</p>
            {photo.questions.length === 0 && <div className="empty">質問はまだありません。</div>}
            {photo.questions.map((q) => (
              <div className="field" key={q.id}>
                <span className="label">{q.reason}</span>
                <p style={{ fontSize: "0.9rem", marginBottom: 6 }}>{q.text}</p>
                <input
                  placeholder={q.answered ? "" : "覚えていることを書く"}
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
              <span className="label">年代</span>
              <input value={era} onChange={(e) => setEra(e.target.value)} placeholder="例: 昭和42年ごろ" />
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

          {/* 場所が決まった写真は、次が語り。開いた状態で出す */}
          <details
            className="card fold"
            ref={storyRef}
            open={Boolean(photo.story) || Boolean(photo.confirmed.place)}
          >
            <summary>
              <h3>語りを聞く</h3>
              <span className={`chip ${photo.story ? "muted" : photo.confirmed.place ? "aka" : "muted"}`}>
                {photo.story ? "記録あり" : photo.confirmed.place ? "いまここ" : "場所が決まってから"}
              </span>
            </summary>
            <p className="lead">
              写真を見ながらの会話をそのまま記録します。人物の関係は AI では確定せず、家族が承認したものだけ残ります。
            </p>

            <div className="row" style={{ marginBottom: 10 }}>
              {recorder.supported ? (
                recorder.recording ? (
                  <button className="btn danger" onClick={recorder.stop}>
                    ■ 録音を止めて記録する
                  </button>
                ) : (
                  <button
                    className="btn"
                    disabled={busy !== null}
                    onClick={() => recorder.start().catch(setError)}
                  >
                    ● 語りを録音する
                  </button>
                )
              ) : (
                <span className="chip muted">この端末では録音が使えません</span>
              )}
            </div>

            <div className="field">
              <span className="label">書き起こしから登録する</span>
              <textarea
                rows={3}
                value={transcript}
                onChange={(e) => setTranscript(e.target.value)}
                placeholder="会話をそのまま貼り付けても構いません"
              />
            </div>
            <button
              className="btn ghost"
              disabled={busy !== null || transcript.trim().length === 0}
              onClick={() =>
                run("story-text", async () => {
                  await api.addStoryText(photo.id, transcript, who);
                  setTranscript("");
                })
              }
            >
              語りとして登録する
            </button>

            {photo.story && (
              <div style={{ marginTop: 16 }}>
                <p style={{ fontSize: "0.92rem" }}>{photo.story.summary}</p>
                {photo.story.transcript && (
                  <p style={{ color: "var(--sub)", fontSize: "0.8rem", marginTop: 6 }}>
                    「{photo.story.transcript}」
                  </p>
                )}
                <div className="row" style={{ marginTop: 10 }}>
                  {photo.story.people.map((p) => (
                    <span key={p.label} className={`chip ${p.confirmed_by_family ? "iro" : "muted"}`}>
                      {p.label}
                      {p.confirmed_by_family ? "（家族が承認）" : "（未確定）"}
                    </span>
                  ))}
                </div>
                {photo.story.people.some((p) => !p.confirmed_by_family) && (
                  <button
                    className="btn small"
                    style={{ marginTop: 10 }}
                    disabled={busy !== null}
                    onClick={() =>
                      run("story-confirm", () =>
                        api.confirmStory(photo.id, {
                          confirmed_by: who,
                          people: photo.story!.people.map((p) => p.label),
                          events: photo.story!.events.map((e) => e.summary),
                        })
                      )
                    }
                  >
                    登場人物と出来事を家族として承認する
                  </button>
                )}
              </div>
            )}
          </details>

        </div>
      </div>
    </>
  );
}
