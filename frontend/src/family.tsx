import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { api } from "./api";
import type { Family } from "./types";

const KEY = "omoide.familyId";
// このブラウザで作った家族の ID。サーバーは家族の一覧を返さないので、ここが唯一の手がかりになる。
// 家族 ID は推測できない長さで、知っている人だけがその家族を開ける（＝ログインの代わり）。
const IDS_KEY = "omoide.familyIds";

// localStorage は使えないこともある（プライベートモードなど）。そのときは記憶しないだけにする
function readIds(): string[] {
  try {
    const ids: unknown = JSON.parse(localStorage.getItem(IDS_KEY) ?? "[]");
    const list = Array.isArray(ids) ? ids.filter((x): x is string => typeof x === "string") : [];
    const current = localStorage.getItem(KEY);
    return current && !list.includes(current) ? [...list, current] : list;
  } catch {
    return [];
  }
}

function writeIds(ids: string[]) {
  try {
    localStorage.setItem(IDS_KEY, JSON.stringify(ids));
  } catch {
    /* 記憶できないだけ */
  }
}

function writeCurrent(id: string | null) {
  try {
    if (id) localStorage.setItem(KEY, id);
    else localStorage.removeItem(KEY);
  } catch {
    /* 記憶できないだけ */
  }
}

interface FamilyState {
  families: Family[];
  family: Family | null;
  loading: boolean;
  select: (id: string) => void;
  refresh: () => Promise<void>;
}

const Ctx = createContext<FamilyState | null>(null);

export function FamilyProvider({ children }: { children: ReactNode }) {
  const [families, setFamilies] = useState<Family[]>([]);
  const [familyId, setFamilyId] = useState<string | null>(() => {
    try {
      return localStorage.getItem(KEY);
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    // 覚えている家族だけを引く。消された家族（404）は忘れる
    const found = await Promise.all(readIds().map((id) => api.getFamily(id).catch(() => null)));
    const list = found.filter((f): f is Family => f !== null);
    writeIds(list.map((f) => f.id));
    setFamilies(list);
    setFamilyId((current) => {
      const stillExists = current && list.some((f) => f.id === current);
      const next = stillExists ? current : list[0]?.id ?? null;
      writeCurrent(next);
      return next;
    });
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh().catch(() => setLoading(false));
  }, [refresh]);

  // 選んだ家族は、このブラウザの「わが家」として覚える（作った直後もここを通る）
  const select = useCallback((id: string) => {
    const ids = readIds();
    if (!ids.includes(id)) writeIds([...ids, id]);
    writeCurrent(id);
    setFamilyId(id);
  }, []);

  const value = useMemo<FamilyState>(
    () => ({
      families,
      family: families.find((f) => f.id === familyId) ?? null,
      loading,
      select,
      refresh,
    }),
    [families, familyId, loading, select, refresh]
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useFamily(): FamilyState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("FamilyProvider の外では使えません");
  return ctx;
}
