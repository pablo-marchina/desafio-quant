"use client";

import { CheckCircle2, CircleOff, LoaderCircle, X } from "lucide-react";

import { Button } from "@/components/ui/button";

type Props = {
  companyName?: string | null;
  loading?: boolean;
  onApprove: () => void;
  onDiscard: () => void;
  onClose: () => void;
};

export function ReviewDecisionDialog({
  companyName,
  loading = false,
  onApprove,
  onDiscard,
  onClose
}: Props) {
  return (
    <div
      aria-modal="true"
      className="fixed inset-0 z-[70] grid place-items-center bg-black/70 px-4 backdrop-blur-sm"
      role="dialog"
    >
      <div className="w-full max-w-md rounded-md border border-border bg-[#0b1118] p-5 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase text-primary">
              Confirmar revisao
            </p>
            <h2 className="mt-2 text-lg font-semibold">
              O que fazer com esta empresa?
            </h2>
          </div>
          <Button
            aria-label="Fechar confirmacao"
            disabled={loading}
            size="icon"
            variant="ghost"
            onClick={onClose}
          >
            <X className="size-4" />
          </Button>
        </div>

        <div className="mt-4 rounded-md border border-border bg-white/[0.02] p-3 text-sm leading-6 text-muted-foreground">
          {companyName || "Esta empresa"} esta marcada como Em Revisao. Escolha
          se ela deve entrar como aprovada no catalogo ou ser descartada da
          base ativa.
        </div>

        <div className="mt-5 grid gap-2 sm:grid-cols-2">
          <Button
            disabled={loading}
            variant="outline"
            onClick={onDiscard}
          >
            {loading ? (
              <LoaderCircle className="mr-2 size-4 animate-spin" />
            ) : (
              <CircleOff className="mr-2 size-4" />
            )}
            Descartar
          </Button>
          <Button disabled={loading} onClick={onApprove}>
            {loading ? (
              <LoaderCircle className="mr-2 size-4 animate-spin" />
            ) : (
              <CheckCircle2 className="mr-2 size-4" />
            )}
            Aprovar
          </Button>
        </div>
      </div>
    </div>
  );
}
