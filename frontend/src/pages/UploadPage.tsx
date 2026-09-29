import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { BatchUploadResult, JobSummary, MetaResponse } from "../types";
import { Dropzone } from "../components/Dropzone";
import { ErrorBanner, InfoBanner } from "../components/ui";
import { formatBytes, formatNumber } from "../lib/format";

const MAX_BATCH = 10;

type ItemStatus = "pending" | "uploading" | "success" | "failed";

interface UploadItem {
  key: string;
  file: File;
  status: ItemStatus;
  jobId?: string;
  rowCount?: number;
  columnCount?: number;
  error?: { code: string; message: string };
}

let itemSeq = 0;

export default function UploadPage() {
  const navigate = useNavigate();
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [items, setItems] = useState<UploadItem[]>([]);
  const [batchError, setBatchError] = useState<ApiError | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    api.get<MetaResponse>("/api/meta").then(setMeta).catch(() => undefined);
  }, []);

  function updateItem(key: string, patch: Partial<UploadItem>) {
    setItems((current) => current.map((item) => (item.key === key ? { ...item, ...patch } : item)));
  }

  function handleFiles(files: File[]) {
    setBatchError(null);
    setNotice(null);
    const accepted = files.slice(0, MAX_BATCH);
    const overflow = files.length - accepted.length;
    const newItems: UploadItem[] = accepted.map((file) => ({
      key: `f${itemSeq++}`,
      file,
      status: "pending",
    }));
    setItems((current) => [...current, ...newItems]);
    if (overflow > 0) {
      setNotice(
        `Only the first ${MAX_BATCH} files were added — ${overflow} file(s) were skipped.`
      );
    }
    void uploadAll(newItems);
  }

  async function uploadAll(toUpload: UploadItem[]) {
    if (toUpload.length === 0) return;
    for (const item of toUpload) {
      updateItem(item.key, { status: "uploading" });
    }
    try {
      const response = await api.uploadBatch(toUpload.map((item) => item.file));
      toUpload.forEach((item, index) => {
        applyResult(item.key, response.results[index], item.file);
      });
      // preserve the original single-file behaviour: jump straight into
      // the dataset when the very first upload is exactly one file
      // (items state here is the pre-batch list, empty on a fresh page)
      if (toUpload.length === 1 && items.length === 0) {
        const result = response.results[0];
        if (result?.status === "uploaded" && result.job_id) {
          setTimeout(() => navigate(`/jobs/${result.job_id}`), 700);
        }
      }
    } catch (err) {
      // the whole request failed (network/timeout/5xx): mark items failed
      const apiError = err instanceof ApiError ? err : new ApiError(0, "network_error", String(err));
      setBatchError(apiError);
      for (const item of toUpload) {
        updateItem(item.key, {
          status: "failed",
          error: { code: apiError.code, message: apiError.message },
        });
      }
    }
  }

  function applyResult(key: string, result: BatchUploadResult | undefined, file: File) {
    if (!result) {
      updateItem(key, { status: "failed", error: { code: "no_result", message: "No result returned for this file." } });
      return;
    }
    if (result.status === "uploaded") {
      updateItem(key, {
        status: "success",
        jobId: result.job_id ?? undefined,
        rowCount: result.row_count ?? undefined,
        columnCount: result.column_count ?? undefined,
        error: undefined,
      });
    } else {
      updateItem(key, {
        status: "failed",
        error: result.error ?? { code: "upload_failed", message: "The file could not be uploaded." },
      });
    }
    void file;
  }

  async function retryItem(item: UploadItem) {
    setBatchError(null);
    updateItem(item.key, { status: "uploading", error: undefined });
    try {
      const job = await api.upload<JobSummary>(item.file);
      updateItem(item.key, {
        status: "success",
        jobId: job.job_id,
        rowCount: job.row_count ?? undefined,
        columnCount: job.column_count ?? undefined,
      });
    } catch (err) {
      const apiError = err instanceof ApiError ? err : new ApiError(0, "network_error", String(err));
      updateItem(item.key, { status: "failed", error: { code: apiError.code, message: apiError.message } });
    }
  }

  const pendingCount = items.filter((i) => i.status === "pending" || i.status === "uploading").length;

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Upload datasets</h1>
          <p>
            CSV, XLSX or XLS — parsed locally by the bundled backend, up to {MAX_BATCH} files at
            once{meta && `, ${meta.max_upload_mb} MB each`}. Each file becomes its own dataset; a
            failed file never blocks the others.
          </p>
        </div>
      </div>

      {batchError && <ErrorBanner message={batchError.message} code={batchError.code} />}
      {notice && <div className="banner banner-info">{notice}</div>}

      <Dropzone onFiles={handleFiles} disabled={false} multiple />

      {items.length > 0 && (
        <div className="card table-wrap mt" data-testid="upload-results">
          <table className="data">
            <thead>
              <tr>
                <th>File</th>
                <th>Status</th>
                <th>Rows × Cols</th>
                <th>Dataset</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.key} data-testid="upload-item" data-status={item.status}>
                  <td className="mono">
                    {item.file.name}
                    <span className="muted"> · {formatBytes(item.file.size)}</span>
                    {item.error && (
                      <div className="muted" style={{ fontSize: 12 }}>
                        {item.error.code}: {item.error.message}
                      </div>
                    )}
                  </td>
                  <td>
                    <span className={`badge ${statusBadge(item.status)}`}>{item.status}</span>
                  </td>
                  <td>
                    {item.status === "success"
                      ? `${formatNumber(item.rowCount)} × ${formatNumber(item.columnCount)}`
                      : "—"}
                  </td>
                  <td>
                    {item.jobId ? (
                      <Link className="mono" style={{ color: "var(--primary)" }} to={`/jobs/${item.jobId}`}>
                        open dataset →
                      </Link>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td>
                    {item.status === "failed" && (
                      <button className="btn btn-sm" onClick={() => retryItem(item)}>
                        Retry
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {pendingCount > 0 && (
        <div className="loading-block" role="status">
          <span className="spinner" aria-hidden="true" /> Uploading {pendingCount} file(s)…
        </div>
      )}

      <div className="mt">
        <InfoBanner>
          <strong>No files of your own?</strong> The repository ships messy demo data:{" "}
          <code>demo-data/sample_customers.csv</code> (duplicate emails, mixed date formats, broken
          phones, cryptic column names), <code>sample_orders.csv</code> and{" "}
          <code>sample_customers_new_batch.csv</code> (for the merge demo), plus an{" "}
          <code>sample_customers.xlsx</code> Excel version — try selecting several at once.
        </InfoBanner>
      </div>
    </div>
  );
}

function statusBadge(status: ItemStatus): string {
  if (status === "success") return "ok";
  if (status === "failed") return "fail";
  if (status === "uploading") return "warn";
  return "";
}
