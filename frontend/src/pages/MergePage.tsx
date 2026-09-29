import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { JobSummary, MergeResponse } from "../types";
import { ErrorBanner, StatCard, SuccessBanner } from "../components/ui";

export default function MergePage() {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [mode, setMode] = useState<"union" | "intersection">("union");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; code?: string } | null>(null);
  const [result, setResult] = useState<MergeResponse | null>(null);

  const refresh = useCallback(() => {
    api.get<JobSummary[]>("/api/jobs").then(setJobs).catch(() => undefined);
  }, []);

  useEffect(refresh, [refresh]);

  const selectedCount = Object.values(selected).filter(Boolean).length;

  async function merge() {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const response = await api.post<MergeResponse>("/api/merge", {
        files: Object.keys(selected)
          .filter((id) => selected[id])
          .map((id) => ({ job_id: id })),
        mode,
      });
      setResult(response);
      setSelected({});
      refresh();
    } catch (err) {
      setError({ message: err instanceof Error ? err.message : String(err), code: (err as { code?: string }).code });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Merge datasets</h1>
          <p>
            Stack two or more uploaded datasets vertically. Use <em>union</em> to keep all columns
            (missing values become null) or <em>intersection</em> to keep shared columns only.
            Column-level renaming for heterogeneous sources is available via the API (
            <span className="mono">POST /api/merge</span> with a per-file mapping).
          </p>
        </div>
      </div>

      {error && <ErrorBanner message={error.message} code={error.code} />}
      {result && (
        <SuccessBanner>
          Merged into <Link to={`/jobs/${result.job_id}`}>{result.filename}</Link> —{" "}
          {result.output_rows} rows × {result.output_columns} columns,{" "}
          {result.null_cells_filled} null cell(s) filled.
        </SuccessBanner>
      )}

      {jobs.length < 2 ? (
        <div className="card empty-state">
          <div className="icon" aria-hidden="true">🧩</div>
          <h3>Need at least two datasets</h3>
          <p>Upload another file to merge (e.g. sample_orders.csv + sample_customers_new_batch.csv).</p>
          <Link className="btn btn-primary" to="/upload">
            Upload a file
          </Link>
        </div>
      ) : (
        <>
          <div className="card table-wrap">
            <table className="data" data-testid="merge-table">
              <thead>
                <tr>
                  <th style={{ width: 40 }}></th>
                  <th>File</th>
                  <th>Rows</th>
                  <th>Columns</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.job_id}>
                    <td>
                      <input
                        type="checkbox"
                        aria-label={`Select ${job.filename}`}
                        checked={Boolean(selected[job.job_id])}
                        onChange={(event) =>
                          setSelected((current) => ({ ...current, [job.job_id]: event.target.checked }))
                        }
                      />
                    </td>
                    <td className="mono">{job.filename}</td>
                    <td>{job.row_count}</td>
                    <td>{job.column_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card card-pad mt row-gap">
            <label className="field" style={{ margin: 0 }}>
              Mode
              <select value={mode} onChange={(event) => setMode(event.target.value as "union" | "intersection")}>
                <option value="union">Union — keep all columns, fill missing with null</option>
                <option value="intersection">Intersection — keep shared columns only</option>
              </select>
            </label>
            <button className="btn btn-primary" onClick={merge} disabled={busy || selectedCount < 2}>
              {busy ? "Merging…" : `Merge ${selectedCount || ""} dataset${selectedCount === 1 ? "" : "s"}`}
            </button>
            {selectedCount < 2 && <span className="muted">Select at least two datasets.</span>}
          </div>
        </>
      )}

      {result && (
        <div className="stat-grid mt">
          <StatCard label="Output rows" value={result.output_rows} tone="positive" />
          <StatCard label="Output columns" value={result.output_columns} />
          <StatCard label="Null cells filled" value={result.null_cells_filled} />
          <StatCard label="Input files" value={result.input_files.length} />
        </div>
      )}
    </div>
  );
}
