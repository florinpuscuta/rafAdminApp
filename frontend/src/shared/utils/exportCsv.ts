/**
 * Export CSV generic — convertește un HTMLTableElement (sau un array de rânduri)
 * într-un CSV descărcat. UTF-8 BOM + separator ";" (Excel RO prefera).
 *
 * Rezultatul se deschide direct în Excel cu fiecare rând pe linia lui și
 * fiecare coloană pe coloana ei.
 */

function escapeCsvValue(v: string): string {
  // Dublează ghilimelele din interiorul valorii
  const esc = v.replace(/"/g, '""');
  // Delimitează cu ghilimele dacă conține ; " sau newline
  if (/[;"\n]/.test(esc)) return `"${esc}"`;
  return esc;
}

export function tableToRows(table: HTMLTableElement): string[][] {
  const rows: string[][] = [];
  const trs = table.querySelectorAll<HTMLTableRowElement>("tr");
  for (const tr of trs) {
    const cells: string[] = [];
    const cellEls = tr.querySelectorAll<HTMLTableCellElement>("th,td");
    for (const c of cellEls) {
      const text = (c.innerText || c.textContent || "").trim().replace(/\s+/g, " ");
      const colspan = Number(c.getAttribute("colspan") || "1");
      cells.push(text);
      for (let i = 1; i < colspan; i++) cells.push("");
    }
    if (cells.length > 0) rows.push(cells);
  }
  return rows;
}

export function rowsToCsv(rows: string[][]): string {
  return rows.map((r) => r.map(escapeCsvValue).join(";")).join("\r\n");
}

export function downloadCsv(filename: string, csv: string): void {
  const BOM = "\uFEFF";
  const blob = new Blob([BOM + csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename.endsWith(".csv") ? filename : `${filename}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** Helper one-shot: ia un table element și îl descarcă drept CSV. */
export function downloadTableAsCsv(
  table: HTMLTableElement | null,
  filename: string,
): boolean {
  if (!table) return false;
  const rows = tableToRows(table);
  if (rows.length === 0) return false;
  downloadCsv(filename, rowsToCsv(rows));
  return true;
}
