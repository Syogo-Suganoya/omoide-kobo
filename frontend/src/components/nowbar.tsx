import { Link } from "react-router-dom";

import type { Photo } from "../types";

/**
 * 写真ページの頭に置く「いまやること」。
 * 画面を開いた人が、下まで読まなくても次の一手が分かるようにする。
 */
export function NowBar({
  photo,
  neighbours,
  onJump,
}: {
  photo: Photo;
  /** 同じアルバムの前後の写真。1枚ずつ片づける作業を続けられるように */
  neighbours: { prev?: Photo; next?: Photo };
  onJump: (target: "confirm" | "story") => void;
}) {
  const { prev, next } = neighbours;

  const nextPhotoLink = next ? (
    <Link className="btn ghost small" to={`/photos/${next.id}`}>
      次の写真へ →
    </Link>
  ) : (
    <Link className="btn ghost small" to={`/albums/${photo.album_id}`}>
      アルバムに戻る
    </Link>
  );

  let body: { text: string; action: React.ReactNode };

  if (photo.status === "failed") {
    body = {
      text: "この写真は直せませんでした。別の写真で試してみてください。",
      action: nextPhotoLink,
    };
  } else if (photo.status !== "awaiting_family" && photo.status !== "confirmed") {
    body = {
      text: "いま直しています。色が戻ると、場所の候補が出ます。",
      action: nextPhotoLink,
    };
  } else if (!photo.confirmed.place) {
    body = {
      text: "場所を確かめてください。AI の候補と、そう考えた理由が下に並んでいます。",
      action: (
        <button className="btn small" onClick={() => onJump("confirm")}>
          場所を決める
        </button>
      ),
    };
  } else if (!photo.story) {
    body = {
      text: `「${photo.confirmed.place}」と決まりました。次は、この写真の話を残せます。`,
      action: (
        <button className="btn small" onClick={() => onJump("story")}>
          語りを残す
        </button>
      ),
    };
  } else {
    body = {
      text: "この写真はひととおり片づきました。",
      action: (
        <>
          <Link className="btn small" to="/trip">
            旅程に入れる
          </Link>
          {nextPhotoLink}
        </>
      ),
    };
  }

  return (
    <div className="now-bar">
      <div className="nav">
        {prev ? (
          <Link to={`/photos/${prev.id}`}>← 前の写真</Link>
        ) : (
          <span className="off">← 前の写真</span>
        )}
        <Link to={`/albums/${photo.album_id}`}>アルバム</Link>
        {next ? (
          <Link to={`/photos/${next.id}`}>次の写真 →</Link>
        ) : (
          <span className="off">次の写真 →</span>
        )}
      </div>
      <div className="task">
        <p>{body.text}</p>
        <div className="row">{body.action}</div>
      </div>
    </div>
  );
}
