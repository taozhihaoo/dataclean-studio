import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type {
  ColumnOps,
  JobDetail,
  NormalizationOp,
  PipelineStep,
  StepReport,
  TransformPreviewResponse,
  TransformResponse,
} from "../types";
import { OP_LABELS } from "../lib/opLabels";
import { DataTable } from "../components/DataTable";
import { ErrorBanner, SuccessBanner } from "../components/ui";

type Draft =
  | { kind: "validate" }
  | { kind: "normalize"; columns: ColumnOps[] }
  | { kind: "dedupe"; mode: "exact" | "columns"; columns: string[]; keep: "first" | "last" }
  | { kind: "rename"; rename: Record<string, string> };

export default function PipelinePage() {
  const { jobId } = useParams();
  const [steps, setSteps] = useState<PipelineStep[]>([]);
  const [detail, setDetail] = useState<JobDetail | null>(null);
  const [busy, setBusy] = useState<"run" | "preview" | null>(null);
  const [error, setError] = useState<{ message: string; code?: string } | null>(null);
  const [result, setResult] = useState<TransformResponse | null>(null);
  const [preview, setPreview] = useState<TransformPreviewResponse | null>(null);

  useEffect(() => {
    api.get<JobDetail>(`/api/jobs/${jobId}`).then(setDetail).catch(() => undefined);
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

  async function run(mode: "run" | "preview") {
    setBusy(mode);
    setError(null);
    if (mode === "run") setResult(null);
    setPreview(null);
    try {
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
          className="btn btn-primary"
          onClick={() => run("run")}
          disabled={busy !== null || steps.length === 0}
        >
          {busy === "run" ? "Running…" : "Run pipeline"}
        </button>
      </div>

      {error && <ErrorBanner message={error.message} code={error.code} />}
      {result && (
        <SuccessBanner>
          Pipeline applied: {result.input_rows} → <strong>{result.output_rows} rows</strong>,{" "}
          {result.changed_cells} cell(s) changed.{" "}
          <Link to={`/jobs/${jobId}/export`}>Continue to export →</Link>
        </SuccessBanner>
      )}

      {steps.length === 0 ? (
        <div className="card empty-state">
          <div className="icon" aria-hidden="true">🧪</div>
          <h3>No steps yet</h3>
          <p>Add steps below — they execute in the order shown.</p>
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
            <button className="btn btn-danger" onClick={() => setSteps([])}>
              Clear pipeline
            </button>
          )}
        </div>
      </div>

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

