"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { createUrlIngestionJob } from "@/lib/api/radar-client";

export function UrlSubmissionForm() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const mutation = useMutation({
    mutationFn: createUrlIngestionJob,
    onSuccess: (job) => router.push(`/jobs/${job.id}`),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    mutation.mutate({ url });
  }

  return (
    <form className="space-y-4" onSubmit={submit}>
      <label className="block text-sm font-medium" htmlFor="startup-url">URL publica da startup</label>
      <input
        className="w-full rounded-md border border-[var(--surface-border)] bg-[#07111f] px-4 py-3 outline-none ring-[var(--accent)] focus:ring-2"
        id="startup-url"
        name="url"
        onChange={(event) => setUrl(event.target.value)}
        placeholder="https://empresa.com"
        required
        type="url"
        value={url}
      />
      {mutation.isError && <p className="text-sm text-[var(--danger)]">{mutation.error.message}</p>}
      <button className="rounded-md bg-[var(--accent)] px-5 py-3 font-semibold text-[#07111f] disabled:cursor-not-allowed disabled:opacity-60" disabled={mutation.isPending} type="submit">
        {mutation.isPending ? "Criando analise..." : "Iniciar analise"}
      </button>
    </form>
  );
}
