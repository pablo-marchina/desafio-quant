import { StartupsTable } from "@/components/startups-table";

export default function StartupsPage() {
  return (
    <main className="mx-auto w-full min-w-0 max-w-[1500px] px-4 py-6 lg:px-8">
      <div className="mb-5">
        <p className="text-xs font-medium text-primary">Catálogo</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">Startups</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Consulte as startups capturadas e acesse seus dados completos.
        </p>
      </div>
      <StartupsTable />
    </main>
  );
}
