import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../api";
import { ErrorBar } from "../components/bits";
import { TodoList, buildTodos } from "../components/todo";
import { useFamily } from "../family";
import type { Album, Photo, Trip } from "../types";

/**
 * 家族がまだ無い人の入口。
 * 最初に名前を考えさせない。入れ物はこちらで用意して、写真の画面まで一気に送る。
 */
function Onboarding({ onDone }: { onDone: (albumId: string) => void }) {
  const { refresh, select } = useFamily();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const family = await api.createFamily("わたしの家族");
      // アルバム作りを別の作業にしない。最初の一冊はこちらで用意する
      const album = await api.createAlbum(family.id, "実家のアルバム");
      await refresh();
      select(family.id);
      onDone(album.id);
    } catch (e) {
      setError(e);
      setBusy(false);
    }
  };

  return (
    <section className="block onboarding">
      <ErrorBar error={error} />
      <h2>はじめまして</h2>
      <p className="lead">
        押すと「実家のアルバム」を1冊用意して、写真を入れる画面までお連れします。
        入力は要りません。
      </p>
      <div className="row">
        <button className="btn" disabled={busy} onClick={start}>
          {busy ? "用意しています…" : "写真を入れる"}
        </button>
      </div>
      <p style={{ color: "var(--sub)", fontSize: "0.82rem", marginTop: 12 }}>
        写真も旅程も、あなたの家族の中だけで共有されます。
        いまは「わたしの家族」という名前にしておきます。共有リンクを渡した相手に見える名前なので、
        気になったらこの画面でいつでも変えられます。
      </p>
    </section>
  );
}

/** 家族の名前。入口で聞かない代わりに、ここで変えられるようにしておく。 */
function FamilyName({ id, name }: { id: string; name: string }) {
  const { refresh } = useFamily();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(name);
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      await api.renameFamily(id, draft.trim() || name);
      await refresh();
      setEditing(false);
    } finally {
      setBusy(false);
    }
  };

  if (!editing) {
    return (
      <span style={{ color: "var(--sub)", fontSize: "0.82rem" }}>
        {name}
        <button
          className="btn ghost small"
          style={{ marginLeft: 8 }}
          onClick={() => {
            setDraft(name);
            setEditing(true);
          }}
        >
          名前を変える
        </button>
      </span>
    );
  }

  return (
    <div className="row" style={{ alignItems: "center" }}>
      <input
        style={{ maxWidth: 220 }}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && !busy && save()}
        placeholder="例: 菅谷家"
        autoFocus
      />
      <button className="btn small" disabled={busy} onClick={save}>
        変える
      </button>
      <button className="btn ghost small" onClick={() => setEditing(false)}>
        やめる
      </button>
    </div>
  );
}

export default function DashboardPage() {
  const { families, family, loading } = useFamily();
  const navigate = useNavigate();
  const [albums, setAlbums] = useState<Album[]>([]);
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [trips, setTrips] = useState<Trip[]>([]);
  const [albumTitle, setAlbumTitle] = useState("");
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async () => {
    if (!family) {
      setAlbums([]);
      setPhotos([]);
      setTrips([]);
      return;
    }
    const [a, p, t] = await Promise.all([
      api.listAlbums(family.id),
      api.listFamilyPhotos(family.id),
      api.listTrips(family.id),
    ]);
    setAlbums(a);
    setPhotos(p);
    setTrips(t);
  }, [family]);

  useEffect(() => {
    load().catch(setError);
  }, [load]);

  // 推定中の写真があるあいだは、勝手に進む様子が見えるように追いかける
  useEffect(() => {
    const working = photos.some((p) =>
      ["uploaded", "estimating"].includes(p.status)
    );
    if (!working || !family) return;
    const timer = setInterval(() => {
      api.listFamilyPhotos(family.id).then(setPhotos).catch(setError);
    }, 2000);
    return () => clearInterval(timer);
  }, [photos, family]);

  const addAlbum = async () => {
    if (!family) return;
    try {
      const album = await api.createAlbum(family.id, albumTitle.trim() || "アルバム");
      setAlbumTitle("");
      navigate(`/albums/${album.id}`);
    } catch (e) {
      setError(e);
    }
  };

  if (loading) return <p className="lead">読み込み中…</p>;
  if (families.length === 0 || !family) {
    return <Onboarding onDone={(albumId) => navigate(`/albums/${albumId}`)} />;
  }

  const todos = buildTodos(photos, albums, trips, family);
  const confirmed = photos.filter((p) => p.confirmed.place).length;

  return (
    <>
      <ErrorBar error={error} />

      <section className="block">
        {/* メニューの呼び名と見出しを揃える。同じ場所を別の名前で呼ばない */}
        <h2>写真を調べる</h2>
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <FamilyName id={family.id} name={family.name} />
          <span style={{ color: "var(--sub)", fontSize: "0.82rem" }}>
            写真 {photos.length}枚 ／ 場所が決まったもの {confirmed}枚
          </span>
        </div>
        <p className="lead">上から片づけていけば、写真を入れるところから旅程まで進みます。</p>
        <TodoList todos={todos} />
      </section>

      <section className="block">
        <h2>アルバム</h2>
        {albums.length === 0 ? (
          <div className="empty">まだアルバムがありません。</div>
        ) : (
          <div className="grid">
            {albums.map((album, i) => {
              const count = photos.filter((p) => p.album_id === album.id).length;
              return (
                <Link
                  key={album.id}
                  to={`/albums/${album.id}`}
                  className={`card ${i % 2 ? "tilt-b" : "tilt-a"}`}
                >
                  <h3>{album.title}</h3>
                  <p style={{ color: "var(--sub)", fontSize: "0.8rem" }}>
                    {count > 0 ? `${count}枚` : "写真はまだありません"}
                  </p>
                </Link>
              );
            })}
          </div>
        )}

        <div className="row" style={{ marginTop: 16 }}>
          <input
            style={{ maxWidth: 260 }}
            value={albumTitle}
            onChange={(e) => setAlbumTitle(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addAlbum()}
            placeholder="新しいアルバムの名前"
          />
          <button className="btn ghost" onClick={addAlbum}>
            アルバムを足す
          </button>
        </div>
      </section>

      {/* 作った旅程が旅の画面にしか無いと、戻ってきたときに見つからない */}
      {trips.length > 0 && (
        <section className="block">
          <h2>組んだ旅程</h2>
          <div className="grid">
            {trips.map((trip, i) => (
              <Link key={trip.id} to="/trip" className={`card ${i % 2 ? "tilt-b" : "tilt-a"}`}>
                <h3>{trip.title}</h3>
                <p style={{ color: "var(--sub)", fontSize: "0.8rem" }}>
                  {trip.date
                    ? new Date(`${trip.date}T00:00:00`).toLocaleDateString("ja-JP", {
                        month: "long",
                        day: "numeric",
                        weekday: "short",
                      })
                    : "日付は未定"}
                  ／{trip.origin} 発／{trip.spots.length}か所
                </p>
              </Link>
            ))}
          </div>
        </section>
      )}
    </>
  );
}
