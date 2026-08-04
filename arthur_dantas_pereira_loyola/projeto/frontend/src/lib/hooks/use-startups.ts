import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { discoverStartupContacts, fetchStartupById, fetchStartupContacts, fetchStartups } from "@/lib/api";

export function useStartups() {
  return useQuery({
    queryKey: ["startups"],
    queryFn: fetchStartups,
    retry: 1,
    staleTime: 15_000,
  });
}

export function useStartup(id: string) {
  return useQuery({
    queryKey: ["startups", id],
    queryFn: () => fetchStartupById(id),
    enabled: !!id,
    retry: 1,
  });
}

export function useContacts(startupId: string) {
  return useQuery({
    queryKey: ["contacts", startupId],
    queryFn: () => fetchStartupContacts(startupId),
    enabled: !!startupId,
    retry: 1,
    staleTime: 60_000,
  });
}

export function useDiscoverContacts() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (startupId: string) => discoverStartupContacts(startupId),
    onSuccess: (_data, startupId) => {
      void qc.invalidateQueries({ queryKey: ["contacts", startupId] });
    },
  });
}
