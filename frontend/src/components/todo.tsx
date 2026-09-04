import { Link } from "react-router-dom";

import type { Album, Family, Photo, PhotoStatus, Trip } from "../types";

export type Todo = {
  /** 作業の段階。案内ページの呼び名と揃える */
  phase: "そろえる" | "確かめる" | "出かける" | "分かち合う";
  title: string;
  detail: string;
  to: string;
  cta: string;
  /** いま進行中で、こちらから押すものが無いもの */
  waiting?: boolean;
};

/**
 * 家族のいまの状態から「次にやること」を組み立てる。
 * 出す順番＝やる順番。並べ替えず、上から片づければ最後まで進む。
 */
/** 修復・推定がまだ途中の状態。家族が手を出す段ではない */
const IN_FLIGHT: PhotoStatus[] = ["uploaded", "restoring", "restored", "estimating"];

export function buildTodos(
  photos: Photo[],
  albums: Album[],
  trips: Trip[],
  family: Family | null
): Todo[] {
  const todos: Todo[] = [];
  const latestAlbum = albums[albums.length - 1];

  const working = photos.filter((p) => IN_FLIGHT.includes(p.status));
  if (working.length > 0) {
    todos.push({
      phase: "そろえる",
      title: `${working.length}枚を直しています`,
      detail: "ノイズを取り、色を戻し、写っている場所を調べています。閉じても進みます。",
      to: `/albums/${working[0].album_id}`,
      cta: "進み具合を見る",
      waiting: true,
    });
  }

  if (photos.length === 0) {
    todos.push({
      phase: "そろえる",
      title: "写真を入れる",
      detail: "アルバムのページをスマホで撮って、まとめて放り込むだけです。",
      to: latestAlbum ? `/albums/${latestAlbum.id}` : "/home",
      cta: latestAlbum ? "写真を入れる" : "アルバムを作る",
    });
    return todos;
  }

  const awaiting = photos.filter((p) => p.status === "awaiting_family");
  if (awaiting.length > 0) {
    todos.push({
      phase: "確かめる",
      title: `${awaiting.length}枚の場所を確かめる`,
      detail: "AI が出した候補と根拠が並んでいます。覚えている人が答えて確定します。",
      to: `/photos/${awaiting[0].id}`,
      cta: "確かめる",
    });
  }

  const noStory = photos.filter((p) => p.confirmed.place && !p.story);
  if (noStory.length > 0) {
    todos.push({
      phase: "確かめる",
      title: `${noStory.length}枚に語りを残す`,
      detail: "写真を見ながらの会話を録音すると、人物や出来事が写真に結びついて残ります。",
      to: `/photos/${noStory[0].id}`,
      cta: "語りを残す",
    });
  }

  const places = photos.filter((p) => p.confirmed.place);
  if (places.length >= 2 && trips.length === 0) {
    todos.push({
      phase: "出かける",
      title: "旅程をつくる",
      detail: `確定した場所が${places.length}か所あります。休憩を挟んだ一日に組み立てられます。`,
      to: "/trip",
      cta: "旅程をつくる",
    });
  }

  const joined = family?.members.filter((m) => m.invite_status === "joined").length ?? 0;
  if (joined <= 1) {
    todos.push({
      phase: "分かち合う",
      title: "家族を招く",
      detail: "招いた家族は、確定や同意に加われます。共有リンクを渡す相手にもなります。",
      to: "/share",
      cta: "招く",
    });
  }

  if (todos.length === 0 && latestAlbum) {
    todos.push({
      phase: "そろえる",
      title: "写真を足す",
      detail: "ひととおり片づきました。次のアルバムに進めます。",
      to: `/albums/${latestAlbum.id}`,
      cta: "写真を足す",
    });
  }

  return todos;
}

export function TodoList({ todos }: { todos: Todo[] }) {
  if (todos.length === 0) return null;
  return (
    <ul className="todo">
      {todos.map((t) => (
        <li key={t.title} className={t.waiting ? "waiting" : ""}>
          <div>
            <span className="phase-tag">{t.phase}</span>
            <b>{t.title}</b>
            <small>{t.detail}</small>
          </div>
          <Link className={`btn ${t.waiting ? "ghost" : ""}`} to={t.to}>
            {t.cta}
          </Link>
        </li>
      ))}
    </ul>
  );
}
