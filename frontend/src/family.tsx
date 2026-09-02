import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { api } from "./api";
import type { Family } from "./types";

const KEY = "omoide.familyId";

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
  const [familyId, setFamilyId] = useState<string | null>(() => localStorage.getItem(KEY));
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const list = await api.listFamilies();
    setFamilies(list);
    setFamilyId((current) => {
      const stillExists = current && list.some((f) => f.id === current);
      const next = stillExists ? current : list[0]?.id ?? null;
      if (next) localStorage.setItem(KEY, next);
      else localStorage.removeItem(KEY);
      return next;
    });
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh().catch(() => setLoading(false));
  }, [refresh]);

  const select = useCallback((id: string) => {
    localStorage.setItem(KEY, id);
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
