import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type {
  ColumnOps,
  JobDetail,
  NormalizationOp,
  PipelineStep,
  RunSummary,
  SavedPipeline,
  StepReport,
  TransformPreviewResponse,
  TransformResponse,
} from "../types";
import { OP_LABELS } from "../lib/opLabels";
import { DataTable } from "../components/DataTable";
import { ErrorBanner, LoadingBlock, SuccessBanner } from "../components/ui";
import { formatDateTime } from "../lib/format";

type Draft =
  | { kind: "validate" }
  | { kind: "normalize"; columns: ColumnOps[] }
  | { kind: "dedupe"; mode: "exact" | "columns"; columns: string[]; keep: "first" | "last" }
  | { kind: "rename"; rename: Record<string, string> };

export default function PipelinePage() {
  const { jobId } = useParams();
  const [steps, setSteps] = useState<PipelineStep[]>([]);
  const [detail, setDetail] = useState<JobDetail | null>(null);
  const [busy, setBusy] = useState<"run" | "preview" | "save" | null>(null);
  const [error, setError] = useState<{ message: string; code?: string } | null>(null);
  const [result, setResult] = useState<TransformResponse | null>(null);
  const [preview, setPreview] = useState<TransformPreviewResponse | null>(null);

  // persistence state
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">("loading");
  const [loadError, setLoadError] = useState<{ message: string; code?: string } | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const savedSnapshot = useRef<string>("");

  const stepsKey = JSON.stringify(steps);
  const isDirty = loadState === "ready" && stepsKey !== savedSnapshot.current;

  useEffect(() => {
    api.get<JobDetail>(`/api/jobs/${jobId}`).then(setDetail).catch(() => undefined);
  }, [jobId]);

  // restore the saved pipeline on entry; surface failures, never swallow them
  useEffect(() => {
    let alive = true;
    setLoadState("loading");
    api
      .get<SavedPipeline>(`/api/jobs/${jobId}/pipeline`)
      .then((saved) => {
        if (!alive) return;
        setSteps(saved.steps);
        savedSnapshot.current = JSON.stringify(saved.steps);
        setSavedAt(saved.updated_at);
        setLoadState("ready");
      })
      .catch((err: { status?: number; message?: string; code?: string }) => {
        if (!alive) return;
        if (err.status === 404) {
          // no pipeline saved yet — a fresh start, not an error
          savedSnapshot.current = "[]";
          setSavedAt(null);
          setLoadState("ready");
          return;
        }
        setLoadError({ message: err.message ?? String(err), code: err.code });
        setLoadState("error");
      });
    return () => {
      alive = false;
    };
  }, [jobId]);

  // hand-off from the dataset page's "apply as rename step" action
  useEffect(() => {
    const pending = sessionStorage.getItem(`dcstudio:pendingRename:${jobId}`);
    if (pending) {
      sessionStorage.removeItem(`dcstudio:pendingRename:${jobId}`);
      try {
        const rename = JSON.parse(pending) as Record<string, string>;
        setSteps((current) => [...current, makeStep("rename", { rename, drop: [], order: [] })]);
      } catch {
        // ignore malformed pending state
      }
    }
  }, [jobId]);

  const columns = useMemo(() => detail?.columns.map((c) => c.name) ?? [], [detail]);

  const save = useCallback(
    async (currentSteps: PipelineStep[]): Promise<boolean> => {
      setBusy("save");
      setError(null);
      try {
        const saved = await api.put<SavedPipeline>(`/api/jobs/${jobId}/pipeline`, {
          steps: currentSteps,
        });
        // the server canonicalizes defaults (e.g. null_tokens), so measure
        // "saved" against the exact editor state we just persisted
        savedSnapshot.current = JSON.stringify(currentSteps);
        setSavedAt(saved.updated_at);
        return true;
      } catch (err) {
        setError({
          message: err instanceof Error ? err.message : String(err),
          code: (err as { code?: string }).code,
        });
        return false;
      } finally {
        setBusy(null);
      }
    },
    [jobId]
  );

  async function clearPipeline() {
    setError(null);
    setPreview(null);
    setResult(null);
    setSteps([]);
    if (savedSnapshot.current !== "[]") {
      try {
        await api.del(`/api/jobs/${jobId}/pipeline`);
      } catch (err) {
        setError({
          message: err instanceof Error ? err.message : String(err),
          code: (err as { code?: string }).code,
        });
        return;
      }
    }
    savedSnapshot.current = "[]";
    setSavedAt(null);
  }

  function addStep(kind: Draft["kind"]) {
    const config =
      kind === "validate"
        ? { rules: [], drop_invalid_rows: false }
        : kind === "normalize"
          ? { columns: [], date_format: "%Y-%m-%d", day_first: false }
          : kind === "dedupe"
            ? { mode: "exact" as const, columns: [], keep: "first" as const }
            : { rename: {}, drop: [], order: [] };
    setSteps((current) => [...current, makeStep(kind, config)]);
  }

  function moveStep(index: number, direction: -1 | 1) {
    setSteps((current) => {
      const target = index + direction;
      if (target < 0 || target >= current.length) return current;
      const next = [...current];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  function toggleStep(id: string) {
    setSteps((current) =>
      current.map((step) => (step.id === id ? { ...step, enabled: !step.enabled } : step))
    );
  }

  function removeStep(id: string) {
    setSteps((current) => current.filter((step) => step.id !== id));
  }

  function updateStep(id: string, config: unknown) {
    setSteps((current) =>
      current.map((step) => (step.id === id ? ({ ...step, config } as PipelineStep) : step))
    );
  }

  function restoreFromRun(run: RunSummary) {
    const pipeline = (run.summary as { pipeline?: { steps?: PipelineStep[] } } | null)?.pipeline;
    if (!pipeline?.steps) return;
    setResult(null);
    setPreview(null);
    setSteps(pipeline.steps);
  }

  async function run(mode: "run" | "preview") {
    setBusy(mode);
    setError(null);
    if (mode === "run") setResult(null);
    setPreview(null);
    try {
      // a run always executes the current editor state; persist it first so
      // "what ran" and "what is saved" can never drift apart silently
      if (mode === "run" && isDirty) {
        const ok = await save(steps);
        if (!ok) {
          setBusy(null);
          return;
        }
      }
      if (mode === "run") {
        setResult(await api.post<TransformResponse>(`/api/jobs/${jobId}/transform`, { steps }));
      } else {
        setPreview(
          await api.post<TransformPreviewResponse>(`/api/jobs/${jobId}/transform/preview`, { steps })
        );
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      const code = (err as { code?: string }).code;
      setError({ message, code });
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Cleaning pipeline</h1>
          <p>
            Steps run top to bottom, always from the original upload — re-run any time.{" "}
            <Link to={`/jobs/${jobId}`} className="muted">
              Dataset →
            </Link>
          </p>
        </div>
        <div className="spacer" />
        <button className="btn" onClick={() => run("preview")} disabled={busy !== null || steps.length === 0}>
          {busy === "preview" ? "Previewing…" : "Preview changes"}
        </button>
        <button
          className="btn"
          onClick={() => save(steps)}
          disabled={busy !== null || steps.length === 0 || !isDirty}
        >
          {busy === "save" ? "Saving…" : "Save pipeline"}
        </button>
        <button
          className="btn btn-primary"
          onClick={() => run("run")}
          disabled={busy !== null || steps.length === 0}
        >
          {busy === "run" ? "Running…" : "Run pipeline"}
        </button>
      </div>

      {loadState === "loading" && <LoadingBlock label="Loading saved pipeline…" />}
      {loadState === "error" && loadError && (
        <ErrorBanner message={`Could not load the saved pipeline: ${loadError.message}`} code={loadError.code} />
      )}

      {loadState === "ready" && (
        <>
          {error && <ErrorBanner message={error.message} code={error.code} />}
          <p className="muted" style={{ marginTop: -8, fontSize: 13 }} data-testid="save-state">
            {isDirty
              ? "Unsaved changes — use “Save pipeline” to keep this configuration."
              : savedAt
                ? `Saved configuration in use (last updated ${formatDateTime(savedAt)}).`
                : "New pipeline — not saved yet."}
          </p>
          {result && (
            <SuccessBanner>
              Pipeline applied: {result.input_rows} → <strong>{result.output_rows} rows</strong>,{" "}
              {result.changed_cells} cell(s) changed.{" "}
              <Link to={`/jobs/${jobId}/export`}>Continue to export →</Link>
            </SuccessBanner>
          )}

          {steps.length === 0 ? (
            <div className="card empty-state" data-testid="pipeline-empty">
              <div className="icon" aria-hidden="true">🧪</div>
              <h3>No steps yet</h3>
              <p>Add steps below — they execute in the order shown. Save keeps them for later.</p>
            </div>
          ) : (
            <div className="card" data-testid="pipeline-steps">
              {steps.map((step, index) => (
                <div key={step.id} className={`pipeline-step${step.enabled ? "" : " disabled"}`}>
                  <span className="grip" aria-hidden="true">⣿</span>
                  <div className="body">
                    <h3>
                      <span className="badge">{index + 1}</span>
                      <span className="badge warn">{step.type}</span>
                      <span className="mono">{step.id}</span>
                    </h3>
                    <StepConfig step={step} columns={columns} onChange={(config) => updateStep(step.id, config)} />
                  </div>
                  <div className="step-actions">
                    <button className="btn btn-sm" onClick={() => toggleStep(step.id)}>
                      {step.enabled ? "Disable" : "Enable"}
                    </button>
                    <button className="btn btn-sm" onClick={() => moveStep(index, -1)} aria-label={`Move ${step.id} up`}>
                      ↑
                    </button>
                    <button className="btn btn-sm" onClick={() => moveStep(index, 1)} aria-label={`Move ${step.id} down`}>
                      ↓
                    </button>
                    <button className="btn btn-sm btn-danger" onClick={() => removeStep(step.id)}>
                      Remove
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="card card-pad mt">
            <h2>Add a step</h2>
            <div className="row-gap">
              <button className="btn" onClick={() => addStep("validate")}>
                Validate rules
              </button>
              <button className="btn" onClick={() => addStep("normalize")}>
                Normalize text / dates / phones
              </button>
              <button className="btn" onClick={() => addStep("dedupe")}>
                Remove duplicates
              </button>
              <button className="btn" onClick={() => addStep("rename")}>
                Rename / map columns
              </button>
              {steps.length > 0 && (
                <button className="btn btn-danger" onClick={clearPipeline}>
                  Clear pipeline
                </button>
              )}
            </div>
          </div>

          <RunHistorySection jobId={jobId!} onRestore={restoreFromRun} />
        </>
      )}

      {preview && (
        <div className="mt" data-testid="preview-results">
          <h2 style={{ fontSize: 17 }}>Preview (first {preview.input_rows} rows, not saved)</h2>
          {preview.steps.map((step) => (
            <StepResultCard key={step.step_id} step={step} />
          ))}
        </div>
      )}

      {result && (
        <div className="mt" data-testid="run-results">
          <h2 style={{ fontSize: 17 }}>Step results</h2>
          {result.steps.map((step) => (
            <StepResultCard key={step.step_id} step={step} />
          ))}
          <div className="card mt">
            <div className="card-pad row-gap" style={{ paddingBottom: 0 }}>
              <strong>Result preview</strong>
              <span className="muted">first {result.preview.length} rows</span>
            </div>
            <DataTable columns={result.columns} rows={result.preview} maxRows={15} />
          </div>
        </div>
      )}
    </div>
  );
}

export function RunHistorySection({
  jobId,
  onRestore,
  limit = 8,
}: {
  jobId: string;
  onRestore?: (run: RunSummary) => void;
  limit?: number;
}) {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .get<RunSummary[]>(`/api/jobs/${jobId}/runs`)
      .then((list) => alive && setRuns(list))
      .catch((err: Error) => alive && setError(err.message));
    return () => {
      alive = false;
    };
  }, [jobId]);

  return (
    <div className="card card-pad mt" data-testid="run-history">
      <h2>Recent runs</h2>
      {error && <ErrorBanner message={error} />}
      {!runs && !error && <LoadingBlock label="Loading run history…" />}
      {runs && runs.length === 0 && (
        <p className="muted" style={{ margin: 0 }}>
          Nothing has run yet. Validation, pipeline, merge and export activity will appear here.
        </p>
      )}
      {runs && runs.length > 0 && (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Kind</th>
                <th>Status</th>
                <th>When</th>
                <th>Summary</th>
                {onRestore && <th></th>}
              </tr>
            </thead>
            <tbody>
              {runs.slice(0, limit).map((run) => (
                <tr key={run.run_id} data-testid="run-row">
                  <td>
                    <span className="badge warn">{run.kind}</span>
                  </td>
                  <td>
                    <span className={`badge ${run.status === "success" ? "ok" : "fail"}`}>
                      {run.status}
                    </span>
                  </td>
                  <td className="muted">{formatDateTime(run.created_at)}</td>
                  <td className="muted" style={{ maxWidth: 420 }}>
                    <RunSummaryText summary={run.summary} />
                  </td>
                  {onRestore && (
                    <td>
                      {run.kind === "transform" &&
                        Boolean((run.summary as { pipeline?: unknown } | null)?.pipeline) && (
                          <button
                            className="btn btn-sm"
                            onClick={() => onRestore(run)}
                            title="Load this run's pipeline configuration into the editor"
                          >
                            Restore config
                          </button>
                        )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function RunSummaryText({ summary }: { summary: Record<string, unknown> | null }) {
  if (!summary) return <span>—</span>;
  const parts: string[] = [];
  if (typeof summary.input_rows === "number" && typeof summary.output_rows === "number") {
    parts.push(`${summary.input_rows} → ${summary.output_rows} rows`);
  }
  if (typeof summary.changed_cells === "number") {
    parts.push(`${summary.changed_cells} cell(s) changed`);
  }
  if (typeof summary.errors_total === "number") {
    parts.push(`${summary.errors_total} error(s)`);
  }
  if (typeof summary.rows_dropped === "number" && summary.rows_dropped > 0) {
    parts.push(`${summary.rows_dropped} row(s) dropped`);
  }
  if (typeof summary.rules === "number") {
    parts.push(`${summary.rules} rule(s)`);
  }
  if (typeof summary.merged_into === "string") {
    parts.push(`merged into ${summary.merged_into.slice(0, 8)}…`);
  }
  if (typeof summary.filename === "string") {
    parts.push(`exported ${summary.filename}`);
  }
  if (parts.length === 0 && Array.isArray(summary.steps)) {
    const stepSummaries = (summary.steps as { summary?: string }[])
      .map((s) => s.summary)
      .filter(Boolean);
    if (stepSummaries.length) parts.push(stepSummaries.join("; "));
  }
  return <span>{parts.length ? parts.join(" · ") : "—"}</span>;
}

function StepConfig({
  step,
  columns,
  onChange,
}: {
  step: PipelineStep;
  columns: string[];
  onChange: (config: unknown) => void;
}) {
  if (step.type === "validate") {
    return (
      <p className="muted" style={{ margin: 0, fontSize: 13.5 }}>
        {step.config.rules.length} rule(s) configured
        {step.config.drop_invalid_rows ? " · invalid rows are dropped" : " · report-only"}. Configure
        rules on the <Link to={`/jobs/../validation`}>Validation tab</Link>, or edit the pipeline
        request directly.
      </p>
    );
  }
  if (step.type === "normalize") {
    const allOps = Object.keys(OP_LABELS) as NormalizationOp[];
    return (
      <div>
        {step.config.columns.length === 0 && (
          <p className="muted" style={{ margin: 0, fontSize: 13.5 }}>
            No column operations yet — add a column below and tick the operations to apply.
          </p>
        )}
        {step.config.columns.map((colOps, index) => (
          <div className="rule-row" key={index} data-testid="normalize-column-row">
            <select
              aria-label={`Column ${index + 1}`}
              value={colOps.column}
              onChange={(event) => {
                const next = [...step.config.columns];
                next[index] = { ...colOps, column: event.target.value };
                onChange({ ...step.config, columns: next });
              }}
            >
              <option value="">Select column…</option>
              {columns.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            {allOps.map((op) => (
              <label key={op} className="row-gap" style={{ gap: 4, fontSize: 12.5 }}>
                <input
                  type="checkbox"
                  aria-label={`${OP_LABELS[op]} on column ${index + 1}`}
                  checked={colOps.operations.includes(op)}
                  onChange={(event) => {
                    const next = [...step.config.columns];
                    next[index] = {
                      ...colOps,
                      operations: event.target.checked
                        ? [...colOps.operations, op]
                        : colOps.operations.filter((o) => o !== op),
                    };
                    onChange({ ...step.config, columns: next });
                  }}
                />
                {OP_LABELS[op]}
              </label>
            ))}
            <button
              className="btn btn-sm btn-danger"
              onClick={() =>
                onChange({
                  ...step.config,
                  columns: step.config.columns.filter((_, i) => i !== index),
                })
              }
            >
              ✕
            </button>
          </div>
        ))}
        <div className="rule-row">
          <button
            className="btn btn-sm"
            onClick={() =>
              onChange({
                ...step.config,
                columns: [...step.config.columns, { column: columns[0] ?? "", operations: ["trim"] }],
              })
            }
          >
            + add column
          </button>
          <span className="muted" style={{ fontSize: 12.5 }}>
            Dates are normalized to <span className="mono">%Y-%m-%d</span>; phones keep digits and a
            leading +.
          </span>
        </div>
      </div>
    );
  }
  if (step.type === "dedupe") {
    return (
      <div className="rule-row">
        <label className="field" style={{ margin: 0 }}>
          Mode
          <select
            value={step.config.mode}
            onChange={(event) =>
              onChange({ ...step.config, mode: event.target.value as "exact" | "columns" })
            }
          >
            <option value="exact">Exact duplicate rows</option>
            <option value="columns">By key column(s)</option>
          </select>
        </label>
        {step.config.mode === "columns" && (
          <select
            multiple
            size={Math.min(4, Math.max(2, columns.length))}
            aria-label="Key columns"
            value={step.config.columns}
            onChange={(event) =>
              onChange({
                ...step.config,
                columns: Array.from(event.target.selectedOptions).map((o) => o.value),
              })
            }
          >
            {columns.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        )}
        <label className="field" style={{ margin: 0 }}>
          Keep
          <select
            value={step.config.keep}
            onChange={(event) =>
              onChange({ ...step.config, keep: event.target.value as "first" | "last" })
            }
          >
            <option value="first">first occurrence</option>
            <option value="last">last occurrence</option>
          </select>
        </label>
      </div>
    );
  }
  // rename
  return (
    <div>
      {Object.entries(step.config.rename).length === 0 && (
        <p className="muted" style={{ margin: 0, fontSize: 13.5 }}>No renames configured.</p>
      )}
      {Object.entries(step.config.rename).map(([from, to]) => (
        <div className="rule-row" key={from}>
          <span className="mono">{from}</span>
          <span className="ba-arrow">→</span>
          <input
            type="text"
            aria-label={`Target name for ${from}`}
            value={to}
            onChange={(event) =>
              onChange({ ...step.config, rename: { ...step.config.rename, [from]: event.target.value } })
            }
            style={{ width: 200 }}
          />
          <button
            className="btn btn-sm btn-danger"
            onClick={() => {
              const next = { ...step.config.rename };
              delete next[from];
              onChange({ ...step.config, rename: next });
            }}
          >
            Remove
          </button>
        </div>
      ))}
      {columns.length > 0 && (
        <div className="rule-row">
          <select
            aria-label="Column to rename"
            value=""
            onChange={(event) => {
              const column = event.target.value;
              if (column && !(column in step.config.rename)) {
                onChange({ ...step.config, rename: { ...step.config.rename, [column]: column } });
              }
            }}
          >
            <option value="">+ add column to rename…</option>
            {columns
              .filter((c) => !(c in step.config.rename))
              .map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
          </select>
        </div>
      )}
    </div>
  );
}

function StepResultCard({ step }: { step: StepReport }) {
  return (
    <div className="card card-pad" style={{ marginBottom: 12 }}>
      <h3 style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 0 }}>
        <span className="badge warn">{step.step_type}</span>
        <span className="mono">{step.step_id}</span>
        <span className={`badge ${step.status === "applied" ? "ok" : ""}`}>{step.status}</span>
      </h3>
      <p style={{ margin: "4px 0 8px" }}>{step.summary}</p>
      <p className="muted" style={{ fontSize: 12.5, margin: 0 }}>
        {step.input_rows} → {step.output_rows} rows
      </p>
      {step.samples.length > 0 && (
        <div className="mt">
          <strong style={{ fontSize: 13 }}>Before → after samples</strong>
          {step.samples.map((sample, index) => (
            <div className="ba-row" key={index}>
              <div>
                <div className="ba-before">{sample.before ?? "∅ null"}</div>
                <div className="ba-meta">
                  row {sample.row}
                  {sample.column ? ` · ${sample.column}` : ""}
                </div>
              </div>
              <div className="ba-arrow">→</div>
              <div className="ba-after">{sample.after ?? "∅ null"}</div>
            </div>
          ))}
        </div>
      )}
      {step.removed_rows.length > 0 && (
        <div className="mt">
          <strong style={{ fontSize: 13 }}>Example removed rows</strong>
          <DataTable columns={Object.keys(step.removed_rows[0])} rows={step.removed_rows} />
        </div>
      )}
    </div>
  );
}

function makeStep(kind: Draft["kind"], config: unknown): PipelineStep {
  const id = `${kind}-${Math.random().toString(36).slice(2, 8)}`;
  if (kind === "validate") {
    return { id, type: "validate", enabled: true, config: config as never };
  }
  if (kind === "normalize") {
    return { id, type: "normalize", enabled: true, config: config as never };
  }
  if (kind === "dedupe") {
    return { id, type: "dedupe", enabled: true, config: config as never };
  }
  return { id, type: "rename", enabled: true, config: config as never };
}

