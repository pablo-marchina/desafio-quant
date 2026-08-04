export function downloadCsv(
  filename: string,
  headers: string[],
  rows: (string | number | null | undefined)[][],
) {
  const bom = "\uFEFF";
  const csv = [
    headers.join(";"),
    ...rows.map((row) =>
      row.map((cell) => {
        if (cell == null) return "";
        const str = String(cell);
        if (str.includes(";") || str.includes('"') || str.includes("\n")) {
          return `"${str.replace(/"/g, '""')}"`;
        }
        return str;
      }).join(";"),
    ),
  ].join("\n");

  const blob = new Blob([bom + csv], { type: "text/csv;charset=utf-8;bom" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${filename}-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}
