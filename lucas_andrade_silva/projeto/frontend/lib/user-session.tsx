"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type ReactNode
} from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type UserSession = {
  userName: string;
  initials: string;
  setUserName: (name: string) => void;
  clearUserName: () => void;
};

const STORAGE_KEY = "start-and-up-user-name";
const UserSessionContext = createContext<UserSession | null>(null);

export function UserSessionProvider({ children }: { children: ReactNode }) {
  const [hydrated, setHydrated] = useState(false);
  const [userName, setUserNameState] = useState("");

  useEffect(() => {
    setUserNameState(sessionStorage.getItem(STORAGE_KEY) || "");
    setHydrated(true);
  }, []);

  const value = useMemo<UserSession>(
    () => ({
      userName,
      initials: initialsFromName(userName),
      setUserName: (name: string) => {
        const cleanName = name.trim().replace(/\s+/g, " ");
        setUserNameState(cleanName);
        sessionStorage.setItem(STORAGE_KEY, cleanName);
      },
      clearUserName: () => {
        setUserNameState("");
        sessionStorage.removeItem(STORAGE_KEY);
      }
    }),
    [userName]
  );

  if (!hydrated) {
    return <div className="min-h-screen bg-background" />;
  }

  return (
    <UserSessionContext.Provider value={value}>
      {userName ? children : <UserNameGate onSubmit={value.setUserName} />}
    </UserSessionContext.Provider>
  );
}

export function useUserSession() {
  const context = useContext(UserSessionContext);
  if (!context) {
    throw new Error("useUserSession must be used within UserSessionProvider");
  }
  return context;
}

function UserNameGate({ onSubmit }: { onSubmit: (name: string) => void }) {
  const [name, setName] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (name.trim()) onSubmit(name);
  }

  return (
    <main className="grid min-h-screen place-items-center bg-background px-4">
      <Card className="w-full max-w-md p-6">
        <div className="mb-5">
          <p className="text-xs font-medium text-primary">Start and Up</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">
            Quem está usando a plataforma?
          </h1>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            O nome informado será usado nos relatórios gerados e na identificação da
            sessão.
          </p>
        </div>
        <form className="space-y-3" onSubmit={submit}>
          <label className="block text-xs text-muted-foreground">
            Nome
            <Input
              autoFocus
              className="mt-2"
              placeholder="Ex.: Lucas"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <Button className="w-full" disabled={!name.trim()} type="submit">
            Iniciar aplicação
          </Button>
        </form>
      </Card>
    </main>
  );
}

function initialsFromName(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "SU";
  const first = parts[0]?.[0] || "";
  const last = parts.length > 1 ? parts[parts.length - 1]?.[0] || "" : "";
  return `${first}${last || parts[0]?.[1] || ""}`.toLocaleUpperCase("pt-BR");
}
