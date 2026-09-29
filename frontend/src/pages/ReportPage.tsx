import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, downloadFile } from "../api/client";
import type { QualityReport } from "../types";
import { ErrorBanner, LoadingBlock, StatCard, TypeBadge } from "../components/ui";
import { formatDateTime, formatNumber } from "../lib/format";

export default function ReportPage() {
  const { jobId } = useParams();
  const [report, setReport] = useState<QualityReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<QualityReport>(`/api/jobs/${jobId}/quality-report`)
      .then(setReport)
      .catch((err: Error) => setError(err.message));
  }, [jobId]);

  if (error) return <ErrorBanner message={error} />;
  if (!report) return <LoadingBlock label="Generating report…" />;

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Data quality report</h1>
          <p>
            Generated {formatDateTime(report.generated_at)} ·{" "}
            <Link to={`/jobs/${jobId}/export`} className="muted">
              ← Export
            </Link>
          </p>
        </div>
        <div className="spacer" />
        <button
          className="btn"
          onClick={() =>
            downloadFile(`/api/jobs/${jobId}/quality-report`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ file_format: "json", filename: "quality_report" }),
            }).catch(() => {
              window.open(`/api/jobs/${jobId}/quality-report`, "_blank");
            })
          }
        >
          Download JSON report
        </button>
      </div>

      <div className="stat-grid">
        <StatCard label="Total rows" value={formatNumber(report.total_rows)} />
        <StatCard label="Total columns" value={report.total_columns} />
        <StatCard label="Null cells" value={formatNumber(report.null_cells_total)} />
        <StatCard
          label="Duplicate rows"
          value={report.duplicate_rows}
          tone={report.duplicate_rows > 0 ? "negative" : "positive"}
        />
        <StatCard
          label="Invalid emails"
          value={report.invalid_email_count}
          tone={report.invalid_email_count > 0 ? "negative" : "positive"}
        />
        <StatCard
          label="Invalid dates"
          value={report.invalid_date_count}
          tone={report.invalid_date_count > 0 ? "negative" : "positive"}
        />
      </div>

      <div className="stat-grid">
        <StatCard
          label="Original rows"
          value={formatNumber(report.original_rows)}
          hint="as uploaded"
        />
        <StatCard
          label="Rows delta"
          value={`${report.rows_delta > 0 ? "+" : ""}${report.rows_delta}`}
          tone={report.rows_delta < 0 ? "negative" : undefined}
          hint="after cleaning"
        />
        <StatCard
          label="Validation"
          value={
            report.validation
              ? `${(report.validation.summary as { errors_total?: number }).errors_total ?? 0} error(s)`
              : "not run"
          }
        />
        <StatCard
          label="Transform"
          value={report.transform ? "applied" : "not run"}
          hint={report.transform ? formatDateTime(report.transform.at) : undefined}
        />
      </div>

      <div className="card table-wrap mt">
        <table className="data" data-testid="report-columns">
          <thead>
            <tr>
              <th>Column</th>
              <th>Type</th>
              <th>Nulls</th>
              <th>Unique</th>
              <th>Invalid</th>
              <th>Samples</th>
            </tr>
          </thead>
          <tbody>
            {report.columns.map((column) => (
              <tr key={column.name}>
                <td className="mono">{column.name}</td>
                <td>
                  <TypeBadge type={column.detected_type} />
                </td>
                <td>
                  {column.null_count}
                  {report.total_rows > 0 && (
                    <span className="muted"> ({Math.round((column.null_count / report.total_rows) * 100)}%)</span>
                  )}
                </td>
                <td>{column.unique_count}</td>
                <td>
                  {column.invalid_count !== undefined && column.invalid_count !== null ? (
                    <span className={`badge ${column.invalid_count > 0 ? "fail" : "ok"}`}>
                      {column.invalid_count}
                    </span>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
                <td className="mono">{column.sample_values.join(" · ") || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
