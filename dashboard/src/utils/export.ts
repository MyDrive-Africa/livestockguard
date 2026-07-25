/**
 * Export utilities for analytics data.
 * Supports CSV download and print-to-PDF.
 */

export interface ExportColumn {
  key: string;
  label: string;
}

/**
 * Download data as a CSV file.
 */
export function downloadCSV(
  data: Record<string, unknown>[],
  columns: ExportColumn[],
  filename: string
): void {
  const header = columns.map((c) => c.label).join(',');
  const rows = data.map((row) =>
    columns
      .map((col) => {
        const value = row[col.key];
        // Escape commas and quotes
        const str = String(value ?? '');
        return str.includes(',') || str.includes('"')
          ? `"${str.replace(/"/g, '""')}"`
          : str;
      })
      .join(',')
  );

  const csv = [header, ...rows].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);

  const link = document.createElement('a');
  link.href = url;
  link.download = `${filename}_${formatDateForFilename()}.csv`;
  link.style.display = 'none';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/**
 * Trigger browser print dialog (for PDF export).
 * Uses @media print CSS to hide non-report elements.
 */
export function printReport(): void {
  window.print();
}

/**
 * Download data as a JSON file (alternative export format).
 */
export function downloadJSON(data: unknown, filename: string): void {
  const json = JSON.stringify(data, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);

  const link = document.createElement('a');
  link.href = url;
  link.download = `${filename}_${formatDateForFilename()}.json`;
  link.style.display = 'none';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function formatDateForFilename(): string {
  return new Date().toISOString().slice(0, 10);
}
