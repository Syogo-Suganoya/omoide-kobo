import { useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";

import type { Job, PhotoStatus } from "../types";

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
  restoring: { text: "修復中", cls: "iro" },
  restored: { text: "修復済", cls: "iro" },
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

export function BeforeAfter({ before, after }: { before: string; after: string }) {
  const [split, setSplit] = useState(50);
  const ref = useRef<HTMLDivElement>(null);

  const move = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.buttons === 0 && event.type === "pointermove") return;
    const box = ref.current?.getBoundingClientRect();
    if (!box) return;
    setSplit(Math.min(100, Math.max(0, ((event.clientX - box.left) / box.width) * 100)));
  };

  return (
    <div
      className="compare"
      ref={ref}
      style={{ ["--split" as string]: `${split}%` }}
      onPointerDown={move}
      onPointerMove={move}
    >
      <img src={before} alt="修復前の白黒写真" />
      <img className="after" src={after} alt="カラー化・修復後の写真" />
      <span className="handle" />
      <span className="tag l">修復前</span>
      <span className="tag r">カラー化・修復後</span>
    </div>
  );
}
