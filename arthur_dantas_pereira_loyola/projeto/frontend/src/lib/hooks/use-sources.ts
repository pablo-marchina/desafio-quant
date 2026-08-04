import { useQuery } from "@tanstack/react-query";
import { fetchRunClaims, fetchRunSources, fetchSources } from "@/lib/api";

export function useSources() {
  return useQuery({
    queryKey: ["sources"],
    queryFn: fetchSources,
    retry: 1,
    staleTime: 15_000,
  });
}

export function useRunSources(id: number | null) {
  return useQuery({
    queryKey: ["runs", id, "sources"],
    queryFn: () => fetchRunSources(id!),
    enabled: id !== null,
    retry: 1,
    staleTime: 15_000,
  });
}

export function useRunClaims(id: number | null) {
  return useQuery({
    queryKey: ["runs", id, "claims"],
    queryFn: () => fetchRunClaims(id!),
    enabled: id !== null,
    retry: 1,
    staleTime: 15_000,
  });
}
