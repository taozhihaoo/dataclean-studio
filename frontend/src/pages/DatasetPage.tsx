import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type {
  InferMappingResponse,
  JobDetail,
  MappingSuggestion,
  MetaResponse,
  PreviewResponse,
} from "../types";
import { DataTable } from "../components/DataTable";
import { TypeBadge, ErrorBanner, InfoBanner, LoadingBlock } from "../components/ui";
import { RunHistorySection } from "./PipelinePage";

type Tab = "preview" | "schema";

export default function DatasetPage() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("preview");
  const [detail, setDetail] = useState<JobDetail | null>(null);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [inference, setInference] = useState<InferMappingResponse | null>(null);
  const [inferenceBusy, setInferenceBusy] = useState(false);
  const [meta, setMeta] = useState<MetaResponse | null>(null);

  const load = useCallback(() => {
    api
      .get<PreviewResponse>(`/api/jobs/${jobId}/preview`)
      .then(setPreview)
      .catch((err: Error) => setError(err.message));
    api
      .get<JobDetail>(`/api/jobs/${jobId}`)
      .then(setDetail)
      .catch(() => undefined);
  }, [jobId]);

  useEffect(() => {
    load();
    api.get<MetaResponse>("/api/meta").then(setMeta).catch(() => undefined);
  }, [load]);

  async function suggestMapping(provider: string) {
    setInferenceBusy(true);
    setError(null);
    try {
      const result = await api.post<InferMappingResponse>(`/api/jobs/${jobId}/infer-mapping`, {
        provider,
        target_schema: meta?.target_schema_suggestions ?? [],
      });
      setInference(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setInferenceBusy(false);
    }
  }

  function applySuggestions(suggestions: MappingSuggestion[]) {
    if (!suggestions.length) return;
    sessionStorage.setItem(
      `dcstudio:pendingRename:${jobId}`,
      JSON.stringify(Object.fromEntries(suggestions.map((s) => [s.source, s.target])))
    );
    navigate(`/jobs/${jobId}/pipeline`);
  }

  if (error && !preview) return <ErrorBanner message={error} />;

  return (
    <div>
      {error && <ErrorBanner message={error} />}

      <div className="tabs" role="tablist" aria-label="Dataset views">
        <button
          role="tab"
          aria-selected={tab === "preview"}
          className={tab === "preview" ? "active" : ""}
          onClick={() => setTab("preview")}
        >
          Preview
        </button>
        <button
          role="tab"
          aria-selected={tab === "schema"}
          className={tab === "schema" ? "active" : ""}
          onClick={() => setTab("schema")}
        >
          Schema & profile
        </button>
      </div>

      {!preview && <LoadingBlock label="Loading preview…" />}

      {preview && tab === "preview" && (
        <div className="card">
          <div className="card-pad row-gap" style={{ paddingBottom: 0 }}>
            <strong>
              {preview.total_rows} rows · {preview.columns.length} columns
            </strong>
            <span className="muted">
              {preview.limited ? `(showing first ${preview.rows.length})` : "(full dataset)"}
            </span>
          </div>
          <DataTable columns={preview.columns} rows={preview.rows} maxRows={50} />
        </div>
      )}

      {preview && tab === "schema" && (
        <>
          <div className="card table-wrap">
            <table className="data" data-testid="schema-table">
              <thead>
                <tr>
                  <th>Column</th>
                  <th>Detected type</th>
                  <th>Nulls</th>
                  <th>Null share</th>
                  <th>Unique</th>
                  <th>Invalid</th>
                  <th>Sample values</th>
                </tr>
              </thead>
              <tbody>
                {(detail?.columns ?? []).map((profile) => {
                  const nullPct = detail?.row_count
                    ? Math.round((profile.null_count / detail.row_count) * 100)
                    : 0;
                  return (
                    <tr key={profile.name}>
                      <td className="mono">{profile.name}</td>
                      <td>
                        <TypeBadge type={profile.detected_type} />
                      </td>
                      <td>{profile.null_count}</td>
                      <td>
                        <span className="nullbar">
                          <div style={{ width: `${nullPct}%` }} />
                        </span>
                      </td>
                      <td>{profile.unique_count}</td>
                      <td>
                        {profile.invalid_count !== undefined && profile.invalid_count !== null ? (
                          <span className={`badge ${profile.invalid_count > 0 ? "fail" : "ok"}`}>
                            {profile.invalid_count} invalid
                          </span>
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                      <td className="mono">
                        {profile.sample_values.join(" · ") || <span className="muted">(empty)</span>}
                      </td>
                    </tr>
                  );
                })}
                {!detail && (
                  <tr>
                    <td colSpan={7}>
                      <LoadingBlock label="Profiling columns…" />
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <InfoBanner>
            Detected types are best-effort heuristics on string values — not a guarantee.{" "}
            {meta?.inference.openai_configured
              ? "The optional OpenAI mapping provider is configured."
              : "No AI key configured — the heuristic mapper works fully offline."}
          </InfoBanner>

          <div className="card card-pad mt">
            <h2>Suggest column mapping</h2>
            <p className="muted" style={{ marginTop: 0 }}>
              Map cryptic source columns (<code>cust_nm</code>, <code>mail</code>, <code>ph_no</code>
              …) to a canonical schema.{" "}
              {meta?.inference.openai_configured
                ? "The optional AI provider sends only column names and up to 3 sample values per column — never the full file."
                : "Runs offline with the built-in heuristic provider; no data leaves your machine."}
            </p>
            <div className="row-gap">
              <button
                className="btn btn-primary"
                onClick={() => suggestMapping("heuristic")}
                disabled={inferenceBusy}
              >
                {inferenceBusy ? "Analyzing…" : "Suggest mapping (heuristic, offline)"}
              </button>
              {meta?.inference.openai_configured && (
                <button className="btn" onClick={() => suggestMapping("openai")} disabled={inferenceBusy}>
                  Suggest with AI (OpenAI)
                </button>
              )}
            </div>
            {inference && (
              <div className="mt" data-testid="inference-results">
                {inference.suggestions.length === 0 ? (
                  <p className="muted">No confident mapping suggestions for this dataset.</p>
                ) : (
                  <>
                    <div className="table-wrap">
                      <table className="data">
                        <thead>
                          <tr>
                            <th>Source column</th>
                            <th></th>
                            <th>Target</th>
                            <th>Confidence</th>
                            <th>Why</th>
                          </tr>
                        </thead>
                        <tbody>
                          {inference.suggestions.map((s) => (
                            <tr key={s.source}>
                              <td className="mono">{s.source}</td>
                              <td className="ba-arrow">→</td>
                              <td>
                                <span className="badge ok">{s.target}</span>
                              </td>
                              <td>
                                <span className="confidence">
                                  <span className="nullbar">
                                    <div style={{ width: `${Math.round(s.confidence * 100)}%` }} />
                                  </span>
                                  {Math.round(s.confidence * 100)}%
                                </span>
                              </td>
                              <td className="muted">{s.rationale}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div className="row-gap mt">
                      <button
                        className="btn btn-primary"
                        onClick={() => applySuggestions(inference.suggestions)}
                      >
                        Apply as rename step in pipeline
                      </button>
                      <span className="muted">provider: {inference.provider}</span>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </>
      )}

      <RunHistorySection jobId={jobId!} limit={5} />
    </div>
  );
}
