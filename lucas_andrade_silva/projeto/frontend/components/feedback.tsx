import { AlertTriangle, DatabaseZap } from "lucide-react";

import { Button } from "@/components/ui/button";

export function ApiErrorState({
  message,
  onRetry
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex min-h-36 flex-col items-center justify-center gap-3 px-5 py-8 text-center">
      <AlertTriangle className="size-6 text-destructive" />
      <div>
        <p className="text-sm font-medium">Não foi possível carregar os dados</p>
        <p className="mt-1 max-w-md text-xs text-muted-foreground">{message}</p>
      </div>
      {onRetry && (
        <Button size="sm" variant="outline" onClick={onRetry}>
          Tentar novamente
        </Button>
      )}
    </div>
  );
}

export function InsufficientData({
  message = "Dados insuficientes para exibir esta informação."
}: {
  message?: string;
}) {
  return (
    <div className="flex min-h-36 flex-col items-center justify-center gap-2 px-5 text-center">
      <DatabaseZap className="size-6 text-muted-foreground" />
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}
