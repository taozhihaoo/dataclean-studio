import type { CellValue } from "../types";

export function DataTable({
  columns,
  rows,
  changedColumns,
  maxRows,
}: {
  columns: string[];
  rows: Record<string, CellValue>[];
  changedColumns?: string[];
  maxRows?: number;
}) {
  const shown = maxRows ? rows.slice(0, maxRows) : rows;
  const changedSet = new Set(changedColumns ?? []);
  return (
    <div className="table-wrap">
      <table className="data" data-testid="data-table">
        <thead>
          <tr>
            <th>#</th>
            {columns.map((column) => (
              <th key={column} className={changedSet.has(column) ? "changed" : undefined}>
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((row, index) => (
            <tr key={index}>
              <td className="null">{index + 1}</td>
              {columns.map((column) => {
                const value = row[column];
                return (
                  <td key={column} className={value === null ? "null" : undefined} title={value ?? "(null)"}>
                    {value === null ? "∅ null" : value === "" ? '""' : value}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
