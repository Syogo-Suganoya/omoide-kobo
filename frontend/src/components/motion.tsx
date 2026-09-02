import { useState } from "react";

import { api } from "../api";
import type { Family, MotionClip } from "../types";

const STATUS: Record<MotionClip["status"], { text: string; cls: string }> = {
  pending_consent: { text: "家族の同意待ち", cls: "aka" },
  denied: { text: "同意が得られませんでした", cls: "muted" },
  generating: { text: "生成中", cls: "iro" },
  ready: { text: "できました", cls: "iro" },
  failed: { text: "失敗", cls: "aka" },
};

/** 生成物の再生。live は mp4、mock は GIF を返すので両方に備える。 */
function Player({ clip }: { clip: MotionClip }) {
  const src = api.motionVideoUrl(clip.id);
  if (clip.media_type.startsWith("video/")) {
    return <video src={src} controls autoPlay loop muted style={{ width: "100%", display: "block" }} />;
  }
  return <img src={src} alt="ウゴクアルバム" style={{ width: "100%", display: "block" }} />;
}

export function MotionPanel({
  family,
  clips,
  busy,
  onRequest,
  onConsent,
}: {
  family: Family | null;
  clips: MotionClip[];
  busy: boolean;
  onRequest: (includesDeceased: boolean) => void;
  onConsent: (motionId: string, uid: string, status: "granted" | "denied") => void;
}) {
  const [includesDeceased, setIncludesDeceased] = useState(true);
  const joined = family?.members.filter((m) => m.invite_status === "joined") ?? [];
  const latest = clips[clips.length - 1];

  return (
    <section className="card">
      <h3>ウゴクアルバム</h3>
      <p className="lead">
        カラー化した写真を数秒だけ動かします。動かすのはその場の空気だけで、
        しゃべらせたり、写っていない動きを足したりはしません。生成物には AI 生成の印が入ります。
      </p>

      {!latest && (
        <>
          <label className="row" style={{ gap: 8, marginBottom: 10, cursor: "pointer" }}>
            <input
              type="checkbox"
              style={{ width: "auto" }}
              checked={includesDeceased}
              onChange={(e) => setIncludesDeceased(e.target.checked)}
            />
            <span style={{ fontSize: "0.86rem" }}>
              亡くなった家族が写っています（参加している家族全員の同意が必要になります）
            </span>
          </label>
          {includesDeceased && joined.length === 0 && (
            <div className="error">
              同意を求める家族がいません。先に「共有と記録」でメンバーを招待し、参加を承諾してもらってください。
            </div>
          )}
          <button
            className="btn"
            disabled={busy || (includesDeceased && joined.length === 0)}
            onClick={() => onRequest(includesDeceased)}
          >
            ウゴクアルバムを作る
          </button>
        </>
      )}

      {clips.map((clip) => (
        <div key={clip.id} style={{ marginTop: 14 }}>
          <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
            <span className={`chip ${STATUS[clip.status].cls}`}>{STATUS[clip.status].text}</span>
            {clip.model && <span className="chip muted">{clip.model}</span>}
          </div>

          {clip.status === "pending_consent" && (
            <table>
              <thead>
                <tr>
                  <th>家族</th>
                  <th>同意</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {clip.consents.map((consent) => (
                  <tr key={consent.uid}>
                    <td style={{ color: "var(--ink)" }}>{consent.name}</td>
                    <td>
                      <span className={`chip ${consent.status === "granted" ? "iro" : "muted"}`}>
                        {consent.status === "granted"
                          ? "同意"
                          : consent.status === "denied"
                            ? "同意しない"
                            : "未回答"}
                      </span>
                    </td>
                    <td>
                      {consent.status === "pending" && (
                        <div className="row">
                          <button
                            className="btn small"
                            disabled={busy}
                            onClick={() => onConsent(clip.id, consent.uid, "granted")}
                          >
                            同意する
                          </button>
                          <button
                            className="btn small ghost"
                            disabled={busy}
                            onClick={() => onConsent(clip.id, consent.uid, "denied")}
                          >
                            同意しない
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {clip.status === "denied" && (
            <p className="notice">
              同意しない家族がいたため、生成していません。写真はそのまま残っています。
            </p>
          )}

          {clip.status === "ready" && (
            <>
              <Player clip={clip} />
              <p style={{ color: "var(--sub)", fontSize: "0.76rem", marginTop: 6 }}>
                生成範囲: {clip.scope}
              </p>
            </>
          )}

          {clip.status === "failed" && <div className="error">{clip.error}</div>}
        </div>
      ))}

      <p style={{ color: "var(--sub)", fontSize: "0.76rem", marginTop: 12 }}>
        依頼・同意・生成の記録は、すべて「共有と記録」の監査ログに残ります。
      </p>
    </section>
  );
}

const VARIANTS = [
  { key: "restored" as const, label: "カラー化" },
  { key: "alt" as const, label: "復元＋再照明" },
];

export function VariantPicker({
  photoId,
  restoredProvider,
  altProvider,
  altSteps,
  preferred,
  showing,
  busy,
  onShow,
  onChoose,
}: {
  photoId: string;
  restoredProvider: string;
  altProvider: string;
  altSteps: string[];
  preferred?: "restored" | "alt" | null;
  showing: "restored" | "alt";
  busy: boolean;
  onShow: (variant: "restored" | "alt") => void;
  onChoose: (variant: "restored" | "alt") => void;
}) {
  const provider = showing === "alt" ? altProvider : restoredProvider;
  return (
    <div style={{ marginTop: 10 }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="row">
          {VARIANTS.map((v) => (
            <button
              key={v.key}
              type="button"
              className={`btn small ${showing === v.key ? "" : "ghost"}`}
              onClick={() => onShow(v.key)}
            >
              {v.label}
              {preferred === v.key ? " ✓" : ""}
            </button>
          ))}
        </div>
        <button
          className="btn small ghost"
          disabled={busy || preferred === showing}
          onClick={() => onChoose(showing)}
          title={`${photoId} の修復結果として採用する`}
        >
          こちらを採用する
        </button>
      </div>
      <p style={{ color: "var(--sub)", fontSize: "0.76rem", marginTop: 6 }}>
        {showing === "alt" ? altSteps.join("／") : "ノイズ除去／退色補正／カラー化"}（{provider}）
        ／ どちらを残すかは家族が決めます
      </p>
    </div>
  );
}
