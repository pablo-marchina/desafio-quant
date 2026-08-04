"use client";

import { LoaderCircle } from "lucide-react";
import { usePathname } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode
} from "react";

type NavigationLoadingContextValue = {
  isLoading: boolean;
  startLoading: () => void;
  stopLoading: () => void;
};

const NavigationLoadingContext =
  createContext<NavigationLoadingContextValue | null>(null);

export function NavigationLoadingProvider({
  children
}: {
  children: ReactNode;
}) {
  const pathname = usePathname();
  const [isLoading, setIsLoading] = useState(false);

  const startLoading = useCallback(() => setIsLoading(true), []);
  const stopLoading = useCallback(() => setIsLoading(false), []);

  useEffect(() => {
    stopLoading();
  }, [pathname, stopLoading]);

  useEffect(() => {
    if (!isLoading) return;
    const timeout = window.setTimeout(stopLoading, 10_000);
    return () => window.clearTimeout(timeout);
  }, [isLoading, stopLoading]);

  const value = useMemo(
    () => ({ isLoading, startLoading, stopLoading }),
    [isLoading, startLoading, stopLoading]
  );

  return (
    <NavigationLoadingContext.Provider value={value}>
      {children}
      {isLoading && (
        <div
          aria-live="polite"
          aria-busy="true"
          className="fixed inset-0 z-[100] grid place-items-center bg-background/80 backdrop-blur-sm"
        >
          <div className="flex items-center gap-3 rounded-md border border-border bg-card px-4 py-3 shadow-glow">
            <LoaderCircle className="size-5 animate-spin text-primary" />
            <span className="text-sm font-medium text-foreground">
              Carregando...
            </span>
          </div>
        </div>
      )}
    </NavigationLoadingContext.Provider>
  );
}

export function useNavigationLoading() {
  const context = useContext(NavigationLoadingContext);
  if (!context) {
    throw new Error(
      "useNavigationLoading must be used inside NavigationLoadingProvider"
    );
  }
  return context;
}
