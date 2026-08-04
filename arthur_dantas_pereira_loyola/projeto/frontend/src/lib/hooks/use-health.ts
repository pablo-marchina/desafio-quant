import { useQuery } from "@tanstack/react-query";
import { fetchHealth } from "@/lib/api";

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    retry: 1,
    staleTime: 30_000,
  });
}
