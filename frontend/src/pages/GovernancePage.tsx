import { useCallback, useEffect, useState } from "react";

import { api } from "../api";
import { ErrorBar } from "../components/bits";
import { useFamily } from "../family";
import type { Album, AuditLog, ShareLink } from "../types";

const ACTION_LABEL: Record<string, string> = {
  upload: "取り込み",
  restore: "修復",
  estimate: "推定",
  family_confirm: "家族の確定",
  story_capture: "語りの記録",
  trip_plan: "旅程作成",
  share: "共有リンクの発行",
  share_view: "共有リンクの閲覧",
  share_revoke: "共有リンクの失効",
  share_scope_change: "共有範囲の変更",
  motion_request: "ウゴクアルバムの依頼",
  motion_consent: "ウゴクアルバムの同意",
  motion_generate: "ウゴクアルバムの生成",
  variant_select: "修復結果の選択",
  delete: "削除",
  external_call: "外部API呼び出し",
};

export default function GovernancePage() {
  const { family, refresh } = useFamily();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [name, setName] = useState("");
  const [relation, setRelation] = useState("長男");
  const [albums, setAlbums] = useState<Album[]>([]);
  const [shares, setShares] = useState<ShareLink[]>([]);
  const [shareTarget, setShareTarget] = useState("");
  const [shareDays, setShareDays] = useState(7);
  const [confirmText, setConfirmText] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async () => {
    if (!family) return;
    const [logList, albumList, shareList] = await Promise.all([
      api.audit(family.id),
      api.listAlbums(family.id),
      api.listShares(family.id),
    ]);
    setLogs(logList);
    setAlbums(albumList);
    setShares(shareList);
  }, [family]);

  useEffect(() => {
    load().catch(setError);
  }, [load]);

  if (!family) return <div className="empty">先に家族をつくってください。</div>;

  const act = async (fn: () => Promise<unknown>, ok: string) => {
    setError(null);
    try {
      await fn();
      setMessage(ok);
      await refresh();
      await load();
    } catch (e) {
      setError(e);
    }
  };

  return (
    <>
      <ErrorBar error={error} />
      {message && <div className="notice">{message}</div>}

      <section className="block">
        <h2>家族メンバー</h2>
        <p className="lead">共有は明示的な招待制です。承諾していない相手には写真を送れません。</p>
        <table>
          <thead>
            <tr>
              <th>名前</th>
              <th>続柄</th>
              <th>状態</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {family.members.map((m) => (
              <tr key={m.uid}>
                <td style={{ color: "var(--ink)" }}>{m.name}</td>
                <td>{m.relation}</td>
                <td>
                  <span className={`chip ${m.invite_status === "joined" ? "iro" : "muted"}`}>
                    {m.invite_status === "joined"
                      ? "参加済"
                      : m.invite_status === "invited"
                        ? "招待中"
                        : "取消済"}
                  </span>
                </td>
                <td>
                  <div className="row">
                    {m.invite_status !== "joined" && (
                      <button
                        className="btn small"
                        onClick={() =>
                          act(
                            () => api.updateInvite(family.id, m.uid, "joined"),
                            `${m.name}さんが参加しました`
                          )
                        }
                      >
                        参加を承諾
                      </button>
                    )}
                    {m.invite_status === "joined" && (
                      <button
                        className="btn small ghost"
                        onClick={() =>
                          act(
                            () => api.updateInvite(family.id, m.uid, "revoked"),
                            `${m.name}さんの共有を止めました`
                          )
                        }
                      >
                        共有をやめる
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="row" style={{ marginTop: 12 }}>
          <input style={{ maxWidth: 200 }} placeholder="名前" value={name} onChange={(e) => setName(e.target.value)} />
          <input
            style={{ maxWidth: 140 }}
            placeholder="続柄"
            value={relation}
            onChange={(e) => setRelation(e.target.value)}
          />
          <button
            className="btn"
            disabled={!name.trim()}
            onClick={() =>
              act(async () => {
                await api.inviteMember(family.id, name.trim(), relation.trim() || "家族");
                setName("");
              }, "招待しました")
            }
          >
            招待する
          </button>
        </div>
      </section>

      <section className="block">
        <h2>共有リンク</h2>
        <p className="lead">
          期限つきの閲覧リンクを作り、家族が普段使っている連絡手段で渡します。
          リンクを開いた人に見えるのは、家族が確定した場所と語りの要約だけです。いつでも止められます。
        </p>
        <div className="card">
          <div className="row">
            <div style={{ flex: 2, minWidth: 220 }}>
              <span className="label">共有するアルバム</span>
              <select value={shareTarget} onChange={(e) => setShareTarget(e.target.value)}>
                <option value="">選んでください</option>
                {albums.map((album) => (
                  <option key={album.id} value={album.id}>
                    {album.title}
                  </option>
                ))}
              </select>
            </div>
            <div style={{ flex: 1, minWidth: 140 }}>
              <span className="label">期限</span>
              <select value={shareDays} onChange={(e) => setShareDays(Number(e.target.value))}>
                <option value={1}>1日</option>
                <option value={7}>7日</option>
                <option value={30}>30日</option>
              </select>
            </div>
          </div>
          <button
            className="btn"
            style={{ marginTop: 14 }}
            disabled={!shareTarget}
            onClick={() =>
              act(async () => {
                const created = await api.createShare({
                  family_id: family.id,
                  target_type: "album",
                  target_id: shareTarget,
                  created_by: "owner",
                  days: shareDays,
                });
                const url = `${location.origin}${created.path}`;
                await navigator.clipboard?.writeText(url).catch(() => undefined);
                setMessage(`共有リンクを作り、コピーしました: ${url}`);
              }, "共有リンクを作りました")
            }
          >
            リンクを作る
          </button>
        </div>

        {shares.length > 0 && (
          <table style={{ marginTop: 14 }}>
            <thead>
              <tr>
                <th>リンク</th>
                <th>期限</th>
                <th>閲覧</th>
                <th>状態</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {shares.map((link) => {
                const expired = new Date(link.expires_at) < new Date();
                const dead = link.revoked || expired;
                return (
                  <tr key={link.id}>
                    <td className="mono">/s/{link.token.slice(0, 8)}…</td>
                    <td>{new Date(link.expires_at).toLocaleDateString("ja-JP")}</td>
                    <td>{link.view_count}回</td>
                    <td>
                      <span className={`chip ${dead ? "muted" : "iro"}`}>
                        {link.revoked ? "停止済" : expired ? "期限切れ" : "有効"}
                      </span>
                    </td>
                    <td>
                      {!dead && (
                        <button
                          className="btn small ghost"
                          onClick={() => act(() => api.revokeShare(link.token), "共有を止めました")}
                        >
                          共有を止める
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

      <section className="block">
        <h2>監査ログ</h2>
        <p className="lead">
          誰が何をしたか、どの外部 API に渡したか、学習オプトアウトの設定まで残します。
        </p>
        {logs.length === 0 ? (
          <div className="empty">まだ記録がありません。</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>時刻</th>
                <th>操作</th>
                <th>実行者</th>
                <th>内容</th>
              </tr>
            </thead>
            <tbody>
              {logs.slice(0, 60).map((log) => (
                <tr key={log.id}>
                  <td style={{ whiteSpace: "nowrap" }}>
                    {new Date(log.created_at).toLocaleTimeString("ja-JP")}
                  </td>
                  <td style={{ color: "var(--ink)" }}>{ACTION_LABEL[log.action] ?? log.action}</td>
                  <td>{log.actor}</td>
                  <td className="mono">{JSON.stringify(log.detail)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="block">
        <h2>削除権</h2>
        <div className="card" style={{ borderLeft: "6px solid var(--aka)" }}>
          <p className="lead">
            この家族の写真・語り・旅程をすべて消します。取り消せません。実行した事実だけが証跡として残ります。
          </p>
          <div className="row">
            <input
              style={{ maxWidth: 260 }}
              placeholder={`確認のため「${family.name}」と入力`}
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
            />
            <button
              className="btn danger"
              disabled={confirmText !== family.name}
              onClick={() =>
                act(async () => {
                  await api.deleteFamily(family.id);
                  setConfirmText("");
                }, "完全に削除しました")
              }
            >
              すべて削除する
            </button>
          </div>
        </div>
      </section>
    </>
  );
}
