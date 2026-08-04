"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { NavigationLoadingProvider } from "@/components/navigation-loading";
import { UserSessionProvider } from "@/lib/user-session";

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1,
            refetchOnWindowFocus: false
          }
        }
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <UserSessionProvider>
        <NavigationLoadingProvider>{children}</NavigationLoadingProvider>
      </UserSessionProvider>
    </QueryClientProvider>
  );
}
