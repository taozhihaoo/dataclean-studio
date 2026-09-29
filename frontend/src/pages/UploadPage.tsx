import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { ApiError } from "../api/client";
import type { JobSummary, MetaResponse } from "../types";
import { Dropzone } from "../components/Dropzone";
import { ErrorBanner, InfoBanner, SuccessBanner } from "../components/ui";
import { formatBytes } from "../lib/format";

export default function UploadPage() {
  const navigate = useNavigate();
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [uploaded, setUploaded] = useState<(JobSummary & { size_bytes?: number }) | null>(null);
  const [currentFile, setCurrentFile] = useState<File | null>(null);

  useEffect(() => {
    api.get<MetaResponse>("/api/meta").then(setMeta).catch(() => undefined);
  }, []);

  async function handleFile(file: File) {
    setError(null);
    setUploaded(null);
    setCurrentFile(file);
    setBusy(true);
    try {
      const job = await api.upload<JobSummary>(file);
      setUploaded(job);
      setTimeout(() => navigate(`/jobs/${job.job_id}`), 700);
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, "network_error", String(err)));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Upload a dataset</h1>
          <p>
            CSV, XLSX or XLS — parsed locally by the bundled backend.
            {meta && ` Up to ${meta.max_upload_mb} MB.`}
          </p>
        </div>
      </div>

      {error && <ErrorBanner message={error.message} code={error.code} />}

      {uploaded && (
        <SuccessBanner>
          <strong>{uploaded.filename}</strong> uploaded: {uploaded.row_count} rows ×{" "}
          {uploaded.column_count} columns
          {currentFile && ` (${formatBytes(currentFile.size)})`} — opening dataset…
        </SuccessBanner>
      )}

      <Dropzone onFile={handleFile} disabled={busy} />

      {busy && (
        <div className="loading-block" role="status">
          <span className="spinner" aria-hidden="true" /> Parsing file…
        </div>
      )}

      <div className="mt">
        <InfoBanner>
          <strong>No file of your own?</strong> The repository ships messy demo data:{" "}
          <code>demo-data/sample_customers.csv</code> (duplicate emails, mixed date formats, broken
          phones, cryptic column names), <code>sample_orders.csv</code> and{" "}
          <code>sample_customers_new_batch.csv</code> (for the merge demo), plus an{" "}
          <code>sample_customers.xlsx</code> Excel version.
        </InfoBanner>
      </div>
    </div>
  );
}
