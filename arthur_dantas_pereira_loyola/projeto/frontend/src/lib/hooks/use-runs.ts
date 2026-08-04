import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchRuns,
  fetchRunById,
  submitRun,
  type SubmitRunPayload,
} from "@/lib/api";

export function useRuns() {
  return useQuery({
    queryKey: ["runs"],
    queryFn: fetchRuns,
    retry: 1,
    staleTime: 10_000,
  });
}

export function useRun(id: number | null) {
  return useQuery({
    queryKey: ["runs", id],
    queryFn: () => fetchRunById(id!),
    enabled: id !== null,
    retry: 1,
    refetchInterval: (query) =>
      query.state.data?.status === "pending" ||
      query.state.data?.status === "running"
        ? 2000
        : false,
  });
}

export function useSubmitRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: SubmitRunPayload) => submitRun(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["runs"] });
    },
  });
}
