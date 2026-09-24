import type { Job, Photo, PhotoStatus } from "../types";

/**
 * 写真につける場所の名前。
 *
 * 家族が確定した名前と、AI がまだ確かめていない候補を、同じ顔で出さない。
 * 候補は括弧でくくって「候補」と添え、断定に見えないようにする（設計書 7-2）。
 */
export function PlaceLabel({ photo }: { photo: Photo }) {
  if (photo.confirmed.place) return <>{photo.confirmed.place}</>;

  const top = photo.estimate?.place_candidates[0];
  if (!top) return <span className="guess">{photo.filename}</span>;

  return (
    <span className="guess">
      「{top.name}」かも <small>候補</small>
    </span>
  );
}

export function Confidence({ value, label }: { value: number; label?: string }) {
  return (
    <div className="conf">
      <span>{label ?? "確度"}</span>
      <span className="bar">
        <i style={{ width: `${Math.round(value * 100)}%` }} />
      </span>
      <span>{Math.round(value * 100)}%</span>
    </div>
  );
}

const STATUS_LABEL: Record<PhotoStatus, { text: string; cls: string }> = {
  uploaded: { text: "取り込み済", cls: "muted" },
  estimating: { text: "推定中", cls: "iro" },
  awaiting_family: { text: "家族の確認待ち", cls: "aka" },
  confirmed: { text: "確定済", cls: "" },
  failed: { text: "失敗", cls: "aka" },
};

export function StatusChip({ status }: { status: PhotoStatus }) {
  const info = STATUS_LABEL[status];
  return <span className={`chip ${info.cls}`}>{info.text}</span>;
}

const JOB_LABEL: Record<Job["status"], { text: string; cls: string }> = {
  queued: { text: "順番待ち", cls: "muted" },
  running: { text: "作業中", cls: "aka" },
  done: { text: "できました", cls: "iro" },
  failed: { text: "一部できませんでした", cls: "aka" },
};

export function JobChip({ status }: { status: Job["status"] }) {
  const info = JOB_LABEL[status];
  return <span className={`chip ${info.cls}`}>{info.text}</span>;
}

export function ErrorBar({ error }: { error: unknown }) {
  if (!error) return null;
  return <div className="error">{error instanceof Error ? error.message : String(error)}</div>;
}

