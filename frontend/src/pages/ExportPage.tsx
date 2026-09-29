import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, downloadFile } from "../api/client";
import type { JobDetail, RunSummary } from "../types";
import { ErrorBanner, InfoBanner, StatCard, SuccessBanner } from "../components/ui";
import { formatDateTime, formatNumber } from "../lib/format";

type ExportFormat = "csv" | "json" | "xlsx";

const FORMAT_HELP: Record<ExportFormat, string> = {
  csv: "UTF-8 with BOM (Excel-friendly). Formula-like cells (=, +, -CMD, @) are neutralized with a leading quote.",
  json: "Array of row objects; nulls are JSON null.",
  xlsx: "Single 'Data' sheet, styled header, frozen first row.",
};

export default function ExportPage() {
  const { jobId } = useParams();
  const [format, setFormat] = useState<ExportFormat>("csv");
  const [filename, setFilename] = useState("cleaned_data");
  const [guardFormulas, setGuardFormulas] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; code?: string } | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [transformRun, setTransformRun] = useState<RunSummary | null>(null);
  const [detail, setDetail] = useState<JobDetail | null>(null);

  useEffect(() => {
    api.get<JobDetail>(`/api/jobs/${jobId}`).then(setDetail).catch(() => undefined);
    api
      .get<RunSummary[]>(`/api/jobs/${jobId}/runs?kind=transform`)
      .then((runs) => setTransformRun(runs[0] ?? null))
      .catch(() => undefined);
  }, [jobId]);

  const derivedDefault = useRef(false);
  useEffect(() => {
    if (detail && !derivedDefault.current) {
      derivedDefault.current = true;
      setFilename(`${detail.filename.replace(/\.[^.]+$/, "")}_clean`);
    }
  }, [detail]);

  async function exportNow() {
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      await downloadFile(`/api/jobs/${jobId}/export`, {
        method: "POST",
        body: JSON.stringify({ file_format: format, filename, guard_formulas: guardFormulas }),
      });
      setDone(`Exported ${filename}.${format}`);
    } catch (err) {
      setError({ message: err instanceof Error ? err.message : String(err), code: (err as { code?: string }).code });
    } finally {
      setBusy(false);
    }
  }

  const transformSummary = transformRun?.summary as
    | { input_rows?: number; output_rows?: number; changed_cells?: number }
    | undefined;

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Export</h1>
          <p>
            Download the current (cleaned) dataset.{" "}
            <Link to={`/jobs/${jobId}/report`} className="muted">
              Quality report →
            </Link>
          </p>
        </div>
      </div>

      {error && <ErrorBanner message={error.message} code={error.code} />}
      {done && <SuccessBanner>Download started: {done}</SuccessBanner>}

      {transformSummary ? (
        <div className="stat-grid">
          <StatCard label="Input rows" value={formatNumber(transformSummary.input_rows)} />
          <StatCard
            label="Output rows"
            value={formatNumber(transformSummary.output_rows)}
            tone="positive"
          />
          <StatCard label="Changed cells" value={formatNumber(transformSummary.changed_cells)} />
          <StatCard label="Columns" value={formatNumber(detail?.column_count)} />
        </div>
      ) : (
        <InfoBanner>
          This dataset has not been transformed yet — exporting will download it as uploaded.
          Configure steps on the <Link to={`/jobs/${jobId}/pipeline`}>pipeline tab</Link> first to
          clean it.
        </InfoBanner>
      )}

      <div className="card card-pad mt">
        <h2>Download</h2>
        <div className="row-gap">
          {(["csv", "json", "xlsx"] as ExportFormat[]).map((option) => (
            <button
              key={option}
              className={`btn${format === option ? " btn-primary" : ""}`}
              onClick={() => setFormat(option)}
              aria-pressed={format === option}
            >
              {option.toUpperCase()}
            </button>
          ))}
        </div>
        <p className="muted" style={{ fontSize: 13 }}>{FORMAT_HELP[format]}</p>
        <div className="row-gap mt">
          <label className="field" style={{ margin: 0 }}>
            Filename (without extension)
            <input
              type="text"
              value={filename}
              onChange={(event) => setFilename(event.target.value)}
              style={{ width: 280 }}
            />
          </label>
          <label className="row-gap" style={{ gap: 6, marginTop: 18 }}>
            <input
              type="checkbox"
              checked={guardFormulas}
              onChange={(event) => setGuardFormulas(event.target.checked)}
            />
            <span className="muted">Guard against formula injection (CSV/XLSX)</span>
          </label>
          <button className="btn btn-primary" onClick={exportNow} disabled={busy} style={{ marginTop: 12 }}>
            {busy ? "Exporting…" : `Export ${format.toUpperCase()}`}
          </button>
        </div>
      </div>

      {transformRun && (
        <p className="muted mt" style={{ fontSize: 12.5 }}>
          Last pipeline run: {formatDateTime(transformRun.created_at)} · run{" "}
          <span className="mono">{transformRun.run_id.slice(0, 8)}</span>
        </p>
      )}
    </div>
  );
}
