import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

export type GuideStep = {
  phase: string;
  title: string;
  detail: ReactNode;
  /** frontend/public/guide/ に置いたスクリーンショット。未配置でも画面は壊れない。 */
  image: string;
};

/** 画面の横に一覧、下に説明。スクショを差し替えるだけで説明が更新できる形にしておく。 */
export function GuideCarousel({ steps }: { steps: GuideStep[] }) {
  const [index, setIndex] = useState(0);
  const [missing, setMissing] = useState<Record<string, boolean>>({});
  const listRef = useRef<HTMLOListElement>(null);
  const step = steps[index];
  const first = index === 0;
  const last = index === steps.length - 1;

  // 端で止める（一覧が長いので、巻き戻ると今どこかを見失う）
  const move = (delta: number) =>
    setIndex((i) => Math.min(steps.length - 1, Math.max(0, i + delta)));

  // 前後送りで選択が一覧の外に出たら、見える位置まで送る
  useEffect(() => {
    listRef.current?.children[index]?.scrollIntoView({ block: "nearest" });
  }, [index]);

  return (
    <div className="guide">
      <ol className="thumbs" aria-label="画面の一覧" ref={listRef}>
        {steps.map((s, i) => (
          <li key={s.title}>
            <button
              type="button"
              className={`thumb ${i === index ? "on" : ""}`}
              aria-current={i === index}
              onClick={() => setIndex(i)}
            >
              <span className="no">{i + 1}</span>
              {missing[s.image] ? (
                <span className="ph" />
              ) : (
                <img src={s.image} alt="" onError={() => setMissing((m) => ({ ...m, [s.image]: true }))} />
              )}
              <span className="label">{s.title}</span>
            </button>
          </li>
        ))}
      </ol>

      <div>
        <div className="shot">
          {missing[step.image] ? (
            <div className="shot-empty">
              <b>{index + 1}</b>
              <span>スクリーンショット準備中</span>
              <code>{step.image}</code>
            </div>
          ) : (
            <img
              src={step.image}
              alt={`${step.title}の画面`}
              onError={() => setMissing((m) => ({ ...m, [step.image]: true }))}
            />
          )}
        </div>

        <div className="shot-nav">
          <button type="button" className="btn small ghost" disabled={first} onClick={() => move(-1)}>
            ← 前
          </button>
          <span className="counter">
            {index + 1} / {steps.length}
          </span>
          <button type="button" className="btn small ghost" disabled={last} onClick={() => move(1)}>
            次 →
          </button>
        </div>

        <div className="shot-caption">
          <span className="phase-tag">{step.phase}</span>
          <h3>{step.title}</h3>
          <p>{step.detail}</p>
        </div>
      </div>
    </div>
  );
}
