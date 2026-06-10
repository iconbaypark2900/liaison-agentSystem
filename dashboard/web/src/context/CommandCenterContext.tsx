"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  Suspense,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import useSWR from "swr";

import { fetchCommandCenter } from "@/lib/fetch-command-center";
import type { CommandCenterState } from "@/lib/command-center-types";
import {
  mergeQueryParams,
  patternFromQuery,
  projectFromQuery,
  taskFromQuery,
} from "@/lib/url-query-helpers";

const PROJECT_DEBOUNCE_MS = 300;

type Ctx = {
  state: CommandCenterState | undefined;
  error: Error | undefined;
  isInitialLoading: boolean;
  isRefreshing: boolean;
  selectedProject: string | null;
  setSelectedProject: (name: string | null) => void;
  selectedTaskId: string | null;
  setSelectedTaskId: (taskId: string | null) => void;
  selectedPatternId: string | null;
  setSelectedPatternId: (patternId: string | null) => void;
  refresh: (hard?: boolean) => void;
};

const CommandCenterContext = createContext<Ctx | null>(null);

function CommandCenterProviderInner({ children }: { children: ReactNode }) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const queryString = searchParams.toString();

  const urlProject = useMemo(() => projectFromQuery(queryString), [queryString]);
  const urlTask = useMemo(() => taskFromQuery(queryString), [queryString]);
  const urlPattern = useMemo(() => patternFromQuery(queryString), [queryString]);

  const [selectedProject, setSelectedProjectState] = useState<string | null>(urlProject);
  const [selectedTaskId, setSelectedTaskIdState] = useState<string | null>(urlTask);
  const [selectedPatternId, setSelectedPatternIdState] = useState<string | null>(urlPattern);
  const [fetchProject, setFetchProject] = useState<string | null>(urlProject);
  const [fetchTask, setFetchTask] = useState<string | null>(urlTask);
  const [fetchPattern, setFetchPattern] = useState<string | null>(urlPattern);

  useEffect(() => {
    setSelectedProjectState((prev) => (prev === urlProject ? prev : urlProject));
  }, [urlProject]);

  useEffect(() => {
    setSelectedTaskIdState((prev) => (prev === urlTask ? prev : urlTask));
  }, [urlTask]);

  useEffect(() => {
    setSelectedPatternIdState((prev) => (prev === urlPattern ? prev : urlPattern));
  }, [urlPattern]);

  useEffect(() => {
    const t = window.setTimeout(() => {
      setFetchProject(selectedProject);
      setFetchTask(selectedTaskId);
      setFetchPattern(selectedPatternId);
    }, PROJECT_DEBOUNCE_MS);
    return () => window.clearTimeout(t);
  }, [selectedProject, selectedTaskId, selectedPatternId]);

  const swrKey = useMemo(
    () =>
      ["command-center", fetchProject ?? "", fetchTask ?? "", fetchPattern ?? ""] as const,
    [fetchProject, fetchTask, fetchPattern]
  );

  const { data, error, isLoading, isValidating, mutate } = useSWR(
    swrKey,
    () =>
      fetchCommandCenter({
        project: fetchProject,
        task: fetchTask,
        pattern: fetchPattern,
      }),
    {
      keepPreviousData: true,
      refreshInterval: (d) => (d?.refresh_sec ?? 30) * 1000,
      revalidateOnFocus: true,
      dedupingInterval: 2000,
    }
  );

  const replaceQuery = useCallback(
    (updates: { project?: string | null; task?: string | null; pattern?: string | null }) => {
      const q = mergeQueryParams(queryString, updates);
      router.replace(q ? `${pathname}?${q}` : pathname, { scroll: false });
    },
    [pathname, queryString, router]
  );

  const setSelectedProject = useCallback(
    (name: string | null) => {
      setSelectedProjectState(name);
      replaceQuery({ project: name });
    },
    [replaceQuery]
  );

  const setSelectedTaskId = useCallback(
    (taskId: string | null) => {
      setSelectedTaskIdState(taskId);
      replaceQuery({ task: taskId });
    },
    [replaceQuery]
  );

  const setSelectedPatternId = useCallback(
    (patternId: string | null) => {
      setSelectedPatternIdState(patternId);
      replaceQuery({ pattern: patternId });
    },
    [replaceQuery]
  );

  // Align selection with server-resolved active task when URL omits task.
  useEffect(() => {
    const resolved = data?.active_task_id;
    if (!resolved || urlTask) return;
    setSelectedTaskIdState((prev) => (prev === resolved ? prev : resolved));
  }, [data?.active_task_id, urlTask]);

  const refresh = useCallback(
    (hard?: boolean) => {
      void mutate(
        () =>
          fetchCommandCenter({
            refresh: true,
            project: fetchProject,
            task: fetchTask,
            pattern: fetchPattern,
          }),
        { revalidate: hard ?? true }
      );
    },
    [fetchPattern, fetchProject, fetchTask, mutate]
  );

  const isInitialLoading = !data && isLoading;
  const isRefreshing = Boolean(data && isValidating);

  const value: Ctx = {
    state: data,
    error: error as Error | undefined,
    isInitialLoading,
    isRefreshing,
    selectedProject,
    setSelectedProject,
    selectedTaskId,
    setSelectedTaskId,
    selectedPatternId,
    setSelectedPatternId,
    refresh,
  };

  return (
    <CommandCenterContext.Provider value={value}>{children}</CommandCenterContext.Provider>
  );
}

export function CommandCenterProvider({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={null}>
      <CommandCenterProviderInner>{children}</CommandCenterProviderInner>
    </Suspense>
  );
}

export function useCommandCenter() {
  const ctx = useContext(CommandCenterContext);
  if (!ctx) throw new Error("useCommandCenter requires CommandCenterProvider");
  return ctx;
}
