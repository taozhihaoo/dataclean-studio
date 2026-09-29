import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { JobSummary, MetaResponse } from "../types";
import { formatDateTime, formatNumber } from "../lib/format";
import {
  EmptyState,
  ErrorBanner,
  InfoBanner,
  LoadingBlock,
  StatCard,
} from "../components/ui";

export default function DashboardPage() {
  const [jobs, setJobs] = useState<JobSummary[] | null>(null);
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api
      .get<JobSummary[]>("/api/jobs")
      .then(setJobs)
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    refresh();
    api.get<MetaResponse>("/api/meta").then(setMeta).catch(() => undefined);
  }, [refresh]);

  async function deleteJob(jobId: string) {
    await api.del(`/api/jobs/${jobId}`);
    refresh();
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Dashboard</h1>
          <p>Your datasets and their cleaning status.</p>
        </div>
        <div className="spacer" />
        <Link className="btn btn-primary" to="/upload">
          + Upload dataset
        </Link>
        <Link className="btn" to="/merge">
          Merge datasets
        </Link>
      </div>

      {error && <ErrorBanner message={error} />}

      {meta && (
        <div className="stat-grid">
          <StatCard label="Datasets" value={jobs ? formatNumber(jobs.length) : "…"} />
          <StatCard label="Max upload" value={`${meta.max_upload_mb} MB`} />
          <StatCard label="Backend" value={`v${meta.version}`} hint="local FastAPI" />
          <StatCard
            label="AI inference"
            value={meta.inference.openai_configured ? "optional · configured" : "heuristic (no key needed)"}
          />
        </div>
      )}

      {jobs === null && !error && <LoadingBlock />}
      {jobs !== null && jobs.length === 0 && (
        <EmptyState
          icon="🧹"
          title="No datasets yet"
          action={
            <Link className="btn btn-primary" to="/upload">
              Upload your first file
            </Link>
          }
        >
          Upload <code>demo-data/sample_customers.csv</code> from the repository to see the full
          cleaning workflow on messy demo data.
        </EmptyState>
      )}

      {jobs !== null && jobs.length > 0 && (
        <div className="card table-wrap">
          <table className="data" data-testid="jobs-table">
            <thead>
              <tr>
                <th>File</th>
                <th>Source</th>
                <th>Status</th>
                <th>Rows</th>
                <th>Columns</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.job_id}>
                  <td>
                    <Link to={`/jobs/${job.job_id}`} className="mono" style={{ color: "var(--primary)" }}>
                      {job.filename}
                    </Link>
                  </td>
                  <td>
                    <span className={`badge ${job.source === "merge" ? "warn" : ""}`}>{job.source}</span>
                  </td>
                  <td>
                    <span className={`badge ${job.status === "transformed" ? "ok" : ""}`}>{job.status}</span>
                  </td>
                  <td>{formatNumber(job.row_count)}</td>
                  <td>{formatNumber(job.column_count)}</td>
                  <td className="muted">{formatDateTime(job.created_at)}</td>
                  <td>
                    <button className="btn btn-sm btn-danger" onClick={() => deleteJob(job.job_id)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {meta && !meta.inference.openai_configured && jobs && jobs.length > 0 && (
        <InfoBanner>
          Tip: after uploading a file with cryptic column names (e.g. <code>cust_nm</code>,{" "}
          <code>mail</code>), use <strong>Suggest column mapping</strong> on the dataset page — the
          built-in heuristic mapping works fully offline.
        </InfoBanner>
      )}
    </div>
  );
}
