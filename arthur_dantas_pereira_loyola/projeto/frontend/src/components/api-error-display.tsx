import { AlertTriangle, RefreshCw } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { ApiError } from "@/lib/api";

interface ApiErrorDisplayProps {
  error: ApiError;
  onRetry?: () => void;
  compact?: boolean;
}

export function ApiErrorDisplay({ error, onRetry, compact }: ApiErrorDisplayProps) {
  const isNetworkError = error.status === 0;

  return (
    <Card className={`border-destructive/30 ${compact ? "p-3" : "p-5"}`}>
      <div className="flex items-start gap-3">
        <AlertTriangle className={`mt-0.5 shrink-0 text-destructive ${compact ? "h-4 w-4" : "h-5 w-5"}`} />
        <div className="min-w-0 space-y-1.5">
          <p className={`font-semibold text-destructive ${compact ? "text-xs" : "text-sm"}`}>
            Falha na comunicação com o backend
          </p>
          <div className={`rounded-md bg-destructive/5 p-2 font-mono ${compact ? "text-[10px]" : "text-xs"}`}>
            <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
              <span className="text-muted-foreground">Endpoint:</span>
              <span className="text-foreground">{error.endpoint}</span>
              <span className="text-muted-foreground">Status:</span>
              <span className="text-foreground">
                {isNetworkError ? "0 (rede)" : `${error.status}`}
              </span>
              {error.message && (
                <>
                  <span className="text-muted-foreground">Detalhe:</span>
                  <span className="text-foreground break-all">{error.message}</span>
                </>
              )}
              {error.code && (
                <>
                  <span className="text-muted-foreground">Código:</span>
                  <span className="text-foreground">{error.code}</span>
                </>
              )}
            </div>
          </div>
          <p className={`text-muted-foreground ${compact ? "text-[10px]" : "text-xs"}`}>
            {isNetworkError
              ? "O servidor FastAPI não está rodando ou não está acessível."
              : "O servidor retornou um erro. Verifique os logs do backend."}
          </p>
          {onRetry && (
            <Button variant="outline" size="sm" className="gap-1.5 text-xs" onClick={onRetry}>
              <RefreshCw className="h-3.5 w-3.5" /> Tentar novamente
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
