import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api";
import { ErrorBar, JobChip, PlaceLabel, StatusChip } from "../components/bits";
import type { Album, Job, Photo } from "../types";

export default function AlbumPage() {
  const { albumId = "" } = useParams();
  const [album, setAlbum] = useState<Album | null>(null);
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [job, setJob] = useState<Job | null>(null);
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    const [a, p] = await Promise.all([api.getAlbum(albumId), api.listPhotos(albumId)]);
    setAlbum(a);
    setPhotos(p);
  }, [albumId]);

  useEffect(() => {
    load().catch(setError);
  }, [load]);

  // 取り込み中はジョブ進行と写真の状態をポーリングする
  useEffect(() => {
    if (!job || job.status === "done" || job.status === "failed") return;
    const timer = setInterval(async () => {
      try {
        const next = await api.getJob(job.id);
        setJob(next);
        setPhotos(await api.listPhotos(albumId));
      } catch (e) {
        setError(e);
      }
    }, 900);
    return () => clearInterval(timer);
  }, [job, albumId]);

  const upload = async (files: FileList | File[] | null) => {
    const list = Array.from(files ?? []).filter((f) => f.type.startsWith("image/"));
    if (list.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.upload(albumId, list);
      setJob(res.job);
      await load();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const progress = job ? Math.round((job.completed / Math.max(1, job.total)) * 100) : 0;
  const awaiting = photos.filter((p) => p.status === "awaiting_family");
  const working = photos.filter((p) => !["awaiting_family", "confirmed", "failed"].includes(p.status));
  const confirmed = photos.filter((p) => p.confirmed.place);

  /** このアルバムを見終えた人の、次の一手 */
  const next =
    awaiting.length > 0
      ? { to: `/photos/${awaiting[0].id}`, cta: "場所を確かめる", text: `${awaiting.length}枚が家族の確認を待っています。` }
      : confirmed.length >= 2
        ? { to: "/trip", cta: "旅程をつくる", text: `場所が決まった写真が${confirmed.length}枚あります。` }
        : { to: "/home", cta: "やることを見る", text: "このアルバムでやることは、いまありません。" };

  return (
    <>
      <ErrorBar error={error} />
      <section className="block">
        <h2>{album?.title ?? "アルバム"}</h2>
        <p className="lead">
          アルバムの写真をまとめて選ぶと、写っている場所と年代の候補を根拠つきで出します。
          預かった写真に手は加えません。確定はあとで家族が行います。
        </p>

        <div
          className={`dropzone ${over ? "over" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setOver(false);
            upload(e.dataTransfer.files);
          }}
          onClick={() => fileRef.current?.click()}
        >
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            multiple
            hidden
            onChange={(e) => upload(e.target.files)}
          />
          {busy ? "取り込んでいます…" : "写真をここにドロップ／タップして選ぶ（複数可・スマホ撮影でOK）"}
        </div>
      </section>

      {job && (
        <section className="block">
          <h2>いま調べています</h2>
          <div className="card">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <JobChip status={job.status} />
              <span style={{ color: "var(--sub)", fontSize: "0.8rem" }}>
                {job.completed} / {job.total} 枚
              </span>
            </div>
            <div className="progress">
              <i style={{ width: `${progress}%` }} />
            </div>
            <ul className="trace">
              {job.steps.map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ul>
          </div>
        </section>
      )}

      <section className="block">
        <h2>写真</h2>
        {/* いまの中身に合わせて言うことを変える。無い札を探させない */}
        {photos.length > 0 && (
        <p className="lead">
          {awaiting.length > 0
              ? `「家族の確認待ち」の札がついた${awaiting.length}枚から開くと、場所を決める作業に進めます。`
              : working.length > 0
                ? "調べているあいだ、ここに進み具合が出ます。終わると「家族の確認待ち」の札がつきます。"
              : "この中の場所はすべて確定しました。旅程に入れられます。"}
        </p>
        )}
        {photos.length === 0 ? (
          <div className="empty">上の枠に写真を入れると、ここに並びます。</div>
        ) : (
          <div className="grid">
            {photos.map((photo, i) => (
              <Link
                key={photo.id}
                to={`/photos/${photo.id}`}
                className={`polaroid ${i % 2 ? "tilt-b" : "tilt-a"}`}
              >
                <img
                  src={api.imageUrl(photo.id)}
                  alt={photo.filename}
                />
                <span className="badge">
                  <StatusChip status={photo.status} />
                </span>
                <span className="cap">
                  <PlaceLabel photo={photo} />
                </span>
              </Link>
            ))}
          </div>
        )}

        {photos.length > 0 && working.length === 0 && (
          <div className="now-bar" style={{ marginTop: 18 }}>
            <div className="task">
              <p>{next.text}</p>
              <div className="row">
                <Link className="btn small" to={next.to}>
                  {next.cta}
                </Link>
              </div>
            </div>
          </div>
        )}
      </section>
    </>
  );
}
