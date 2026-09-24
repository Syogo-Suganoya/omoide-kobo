import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { api } from "../api";
import type { SharedView } from "../types";

/** 家族が発行した期限付きリンクの閲覧画面。ログイン不要・読むだけ。 */
export default function SharedPage() {
  const { token = "" } = useParams();
  const [view, setView] = useState<SharedView | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .viewShared(token)
      .then(setView)
      .catch((e: Error) =>
        setError(
          e.message.includes("410")
            ? "この共有リンクは期限切れ、または家族によって共有が止められています。"
            : "共有リンクが見つかりませんでした。"
        )
      );
  }, [token]);

  if (error) return <div className="empty">{error}</div>;
  if (!view) return <div className="empty">読み込み中…</div>;

  return (
    <>
      <section className="block">
        <h2>{view.title}</h2>
        <p className="lead">
          家族が共有した思い出です。{new Date(view.expires_at).toLocaleDateString("ja-JP")} まで見られます。
        </p>
      </section>

      <div className="grid">
        {view.photos.map((photo, i) => (
          <figure key={photo.id} className={`polaroid ${i % 2 ? "tilt-b" : "tilt-a"}`}>
            {photo.has_image && <img src={api.sharedImageUrl(token, photo.id)} alt={photo.place ?? ""} />}
            <figcaption className="cap">{photo.place ?? "撮影地は確認中"}</figcaption>
          </figure>
        ))}
      </div>

    </>
  );
}
