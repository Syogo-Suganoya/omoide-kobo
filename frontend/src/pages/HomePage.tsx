import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import { ErrorBar } from "../components/bits";
import { useFamily } from "../family";
import type { AgentsResponse, Album } from "../types";

export default function HomePage() {
  const { families, family, loading, refresh, select } = useFamily();
  const [albums, setAlbums] = useState<Album[]>([]);
  const [agents, setAgents] = useState<AgentsResponse | null>(null);
  const [familyName, setFamilyName] = useState("");
  const [albumTitle, setAlbumTitle] = useState("実家のアルバム");
  const [error, setError] = useState<unknown>(null);

  const loadAlbums = useCallback(async () => {
    if (!family) return setAlbums([]);
    setAlbums(await api.listAlbums(family.id));
  }, [family]);

  useEffect(() => {
    loadAlbums().catch(setError);
  }, [loadAlbums]);

  useEffect(() => {
    api.agents().then(setAgents).catch(setError);
  }, []);

  const createFamily = async () => {
    try {
      const created = await api.createFamily(familyName.trim() || "わたしの家族");
      setFamilyName("");
      await refresh();
      select(created.id);
    } catch (e) {
      setError(e);
    }
  };

  const createAlbum = async () => {
    if (!family) return;
    try {
      await api.createAlbum(family.id, albumTitle.trim() || "アルバム");
      await loadAlbums();
    } catch (e) {
      setError(e);
    }
  };

  return (
    <>
      <ErrorBar error={error} />

      <section className="block">
        <h2>家族</h2>
        {loading ? (
          <p className="lead">読み込み中…</p>
        ) : families.length === 0 ? (
          <p className="lead">
            はじめに家族をつくります。写真・語り・旅程はこの家族の中だけで共有されます。
          </p>
        ) : (
          <p className="lead">
            いま開いているのは「{family?.name}」です。メンバーの招待は
            <Link to="/governance"> 共有と記録 </Link>から。
          </p>
        )}
        <div className="row">
          <input
            style={{ maxWidth: 280 }}
            placeholder="家族の名前（例: 菅谷家）"
            value={familyName}
            onChange={(e) => setFamilyName(e.target.value)}
          />
          <button className="btn" onClick={createFamily}>
            家族をつくる
          </button>
        </div>
      </section>

      {family && (
        <section className="block">
          <h2>アルバム</h2>
          <p className="lead">
            実家のアルバムを一冊ずつ作り、写真をまとめて取り込みます。取り込むと修復と場所推定が自動で進みます。
          </p>
          <div className="row" style={{ marginBottom: 16 }}>
            <input
              style={{ maxWidth: 280 }}
              value={albumTitle}
              onChange={(e) => setAlbumTitle(e.target.value)}
              placeholder="アルバム名"
            />
            <button className="btn" onClick={createAlbum}>
              アルバムを作る
            </button>
          </div>

          {albums.length === 0 ? (
            <div className="empty">まだアルバムがありません。</div>
          ) : (
            <div className="grid">
              {albums.map((album, i) => (
                <Link
                  key={album.id}
                  to={`/albums/${album.id}`}
                  className={`card ${i % 2 ? "tilt-b" : "tilt-a"}`}
                >
                  <h3>{album.title}</h3>
                  <p style={{ color: "var(--sub)", fontSize: "0.8rem" }}>
                    作成 {new Date(album.created_at).toLocaleDateString("ja-JP")}
                  </p>
                </Link>
              ))}
            </div>
          )}
        </section>
      )}

      {agents && (
        <section className="block">
          <h2>はたらくエージェント</h2>
          <p className="lead">
            オーケストレータが取り込み→修復→推定→旅程を進めます。「提示まで」の担当は、家族が確定するまで先へ進みません。
          </p>
          <div className="grid">
            {agents.roster.map((agent) => (
              <div className="card tight" key={agent.name}>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <h3 style={{ margin: 0 }}>{agent.name}</h3>
                  <span className={`chip ${agent.autonomy === "autonomous" ? "iro" : "aka"}`}>
                    {agent.autonomy === "autonomous" ? "自律" : "提示まで"}
                  </span>
                </div>
                <p style={{ color: "var(--sub)", fontSize: "0.82rem" }}>{agent.role}</p>
              </div>
            ))}
          </div>
          <div className="card tight" style={{ marginTop: 14 }}>
            <div className="row">
              {Object.entries(agents.modes).map(([key, mode]) => (
                <span key={key} className={`chip ${mode === "live" ? "iro" : "muted"}`}>
                  {key}: {mode}
                </span>
              ))}
              <span className={`chip ${agents.adk.active ? "iro" : "muted"}`}>
                ADK: {agents.adk.active ? "有効" : agents.adk.available ? "待機" : "未導入"}
              </span>
            </div>
            <p style={{ color: "var(--sub)", fontSize: "0.78rem", marginTop: 8 }}>
              ポリシー: {agents.policy}
              {agents.adk.reason ? `／${agents.adk.reason}` : ""}
            </p>
          </div>
        </section>
      )}
    </>
  );
}
