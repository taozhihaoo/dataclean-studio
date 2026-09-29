import { useEffect, useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import type { JobDetail } from "../types";
import { api } from "../api/client";
import { formatBytes, formatNumber } from "../lib/format";
import { LoadingBlock, ErrorBanner, StatCard } from "../components/ui";

const STEPS = [
  { path: "", label: "Dataset", num: 1 },
  { path: "pipeline", label: "Clean & Transform", num: 2 },
  { path: "validation", label: "Validation", num: 3 },
  { path: "export", label: "Export", num: 4 },
  { path: "report", label: "Quality Report", num: 5 },
];

export default function JobLayout({ jobId, children }: { jobId: string; children: ReactNode }) {
  return (
    <div>
      <Stepper jobId={jobId} />
      <JobHeader jobId={jobId} />
      {children}
    </div>
  );
}

function Stepper({ jobId }: { jobId: string }) {
  return (
    <nav className="stepper" aria-label="Workflow steps">
      {STEPS.map((step) => (
        <NavLink
          key={step.path}
          to={step.path ? `/jobs/${jobId}/${step.path}` : `/jobs/${jobId}`}
          end={step.path === ""}
        >
          <span className="num">{step.num}</span>
          {step.label}
        </NavLink>
      ))}
    </nav>
  );
}

function JobHeader({ jobId }: { jobId: string }) {
  const [job, setJob] = useState<JobDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .get<JobDetail>(`/api/jobs/${jobId}`)
      .then((detail) => alive && setJob(detail))
      .catch((err: Error) => alive && setError(err.message));
    return () => {
      alive = false;
    };
  }, [jobId]);

  if (error) return <ErrorBanner message={error} />;
  if (!job) return <LoadingBlock label="Loading dataset…" />;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>
            {job.filename}
            {job.source === "merge" && <span className="badge warn" style={{ marginLeft: 10 }}>merged</span>}
            {job.is_transformed && <span className="badge ok" style={{ marginLeft: 10 }}>cleaned</span>}
          </h1>
          <p className="mono">job {job.job_id}</p>
        </div>
      </div>
      <div className="stat-grid">
        <StatCard label="Rows" value={formatNumber(job.row_count)} />
        <StatCard label="Columns" value={formatNumber(job.column_count)} />
        <StatCard label="Uploaded size" value={formatBytes(job.size_bytes)} />
        <StatCard
          label="Status"
          value={<span className={`badge ${job.is_transformed ? "ok" : ""}`}>{job.status}</span>}
        />
      </div>
    </>
  );
}
