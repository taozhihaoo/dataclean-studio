import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { JobDetail, RuleConfig, RuleResult, ValidateResponse } from "../types";
import { ErrorBanner, StatCard, SuccessBanner } from "../components/ui";

const RULE_TYPES = [
  { value: "required", label: "Required (not null)" },
  { value: "email", label: "Valid email" },
  { value: "numeric_range", label: "Numeric range" },
  { value: "string_length", label: "String length" },
  { value: "date", label: "Parseable date" },
  { value: "regex", label: "Matches regex" },
  { value: "allowed_values", label: "Allowed values" },
] as const;

const PRESETS: Record<string, Omit<RuleConfig, "column">> = {
  required: { rule: "required" },
  email: { rule: "email" },
  numeric_range: { rule: "numeric_range", min: 0, max: 120 },
  string_length: { rule: "string_length", min_length: 1, max_length: 100 },
  date: { rule: "date" },
  regex: { rule: "regex", pattern: "" },
  allowed_values: { rule: "allowed_values", values: [] },
};

export default function ValidationPage() {
  const { jobId } = useParams();
  const [detail, setDetail] = useState<JobDetail | null>(null);
  const [rules, setRules] = useState<RuleConfig[]>([]);
  const [dropInvalid, setDropInvalid] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; code?: string } | null>(null);
  const [result, setResult] = useState<ValidateResponse | null>(null);

  useEffect(() => {
    api.get<JobDetail>(`/api/jobs/${jobId}`).then(setDetail).catch(() => undefined);
  }, [jobId]);

  const columns = useMemo(() => detail?.columns.map((c) => c.name) ?? [], [detail]);

  const addRule = useCallback(
    (column?: string, preset?: keyof typeof PRESETS) => {
      const targetColumn = column ?? columns[0];
      const ruleType = preset ?? "required";
      if (!targetColumn) return;
      setRules((current) => [...current, { column: targetColumn, ...PRESETS[ruleType] } as RuleConfig]);
    },
    [columns]
  );

  function updateRule(index: number, patch: Partial<RuleConfig>) {
    setRules((current) => current.map((rule, i) => (i === index ? { ...rule, ...patch } : rule)));
  }

  function changeRuleType(index: number, ruleType: RuleConfig["rule"]) {
    updateRule(index, PRESETS[ruleType] as Partial<RuleConfig>);
  }

  async function run() {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(
        await api.post<ValidateResponse>(`/api/jobs/${jobId}/validate`, {
          rules,
          drop_invalid_rows: dropInvalid,
        })
      );
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
          <h1>Validation rules</h1>
          <p>
            Rules apply to non-null values; use <em>Required</em> to catch empties.{" "}
            <Link to={`/jobs/${jobId}/pipeline`} className="muted">
              Pipeline →
            </Link>
          </p>
        </div>
        <div className="spacer" />
        <button
          className="btn btn-primary"
          onClick={run}
          disabled={busy || rules.length === 0}
        >
          {busy ? "Validating…" : "Run validation"}
        </button>
      </div>

      {error && <ErrorBanner message={error.message} code={error.code} />}
      {result && (
        <SuccessBanner>
          {result.passed ? (
            <>All rules passed — no errors in {result.total_rows} rows.</>
          ) : (
            <>
              {result.error_count_total} error(s) found in {result.total_rows} rows.
              {result.rows_dropped > 0 && ` ${result.rows_dropped} invalid row(s) removed.`}
            </>
          )}
        </SuccessBanner>
      )}

      <div className="card card-pad">
        <h2>Rules</h2>
        {rules.length === 0 && (
          <p className="muted">No rules yet — add one below (e.g. email on the mail column).</p>
        )}
        {rules.map((rule, index) => (
          <div className="rule-row" key={index} data-testid="rule-row">
            <select
              aria-label="Rule column"
              value={rule.column}
              onChange={(event) => updateRule(index, { column: event.target.value })}
            >
              {columns.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            <select
              aria-label="Rule type"
              value={rule.rule}
              onChange={(event) => changeRuleType(index, event.target.value as RuleConfig["rule"])}
            >
              {RULE_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
            {rule.rule === "numeric_range" && (
              <>
                <input
                  type="number"
                  aria-label="Min"
                  placeholder="min"
                  style={{ width: 90 }}
                  value={rule.min ?? ""}
                  onChange={(event) => updateRule(index, { min: event.target.value === "" ? null : Number(event.target.value) })}
                />
                <input
                  type="number"
                  aria-label="Max"
                  placeholder="max"
                  style={{ width: 90 }}
                  value={rule.max ?? ""}
                  onChange={(event) => updateRule(index, { max: event.target.value === "" ? null : Number(event.target.value) })}
                />
              </>
            )}
            {rule.rule === "string_length" && (
              <>
                <input
                  type="number"
                  aria-label="Min length"
                  placeholder="min len"
                  style={{ width: 90 }}
                  value={rule.min_length ?? ""}
                  onChange={(event) => updateRule(index, { min_length: event.target.value === "" ? null : Number(event.target.value) })}
                />
                <input
                  type="number"
                  aria-label="Max length"
                  placeholder="max len"
                  style={{ width: 90 }}
                  value={rule.max_length ?? ""}
                  onChange={(event) => updateRule(index, { max_length: event.target.value === "" ? null : Number(event.target.value) })}
                />
              </>
            )}
            {rule.rule === "regex" && (
              <input
                type="text"
                aria-label="Regex pattern"
                placeholder="^[A-Z]{2}\\d{2}$"
                style={{ width: 220 }}
                className="mono"
                value={rule.pattern ?? ""}
                onChange={(event) => updateRule(index, { pattern: event.target.value })}
              />
            )}
            {rule.rule === "allowed_values" && (
              <AllowedValuesInput
                values={rule.values ?? []}
                onChange={(values) => updateRule(index, { values })}
              />
            )}
            <button
              className="btn btn-sm btn-danger"
              onClick={() => setRules((current) => current.filter((_, i) => i !== index))}
            >
              Remove
            </button>
          </div>
        ))}
        <div className="row-gap mt">
          <select
            aria-label="Add rule for column"
            value=""
            onChange={(event) => {
              if (event.target.value) {
                const [column, preset] = event.target.value.split("::");
                addRule(column, preset as keyof typeof PRESETS);
              }
            }}
            style={{ maxWidth: 340 }}
          >
            <option value="">+ add rule…</option>
            {columns.flatMap((column) =>
              RULE_TYPES.map((t) => (
                <option key={`${column}::${t.value}`} value={`${column}::${t.value}`}>
                  {column} — {t.label}
                </option>
              ))
            )}
          </select>
          <label className="row-gap" style={{ gap: 6 }}>
            <input
              type="checkbox"
              checked={dropInvalid}
              onChange={(event) => setDropInvalid(event.target.checked)}
            />
            <span className="muted">Drop rows that fail any rule (applied to the dataset)</span>
          </label>
        </div>
      </div>

      {result && (
        <div className="mt" data-testid="validation-results">
          <div className="stat-grid">
            <StatCard label="Rows checked" value={result.total_rows} />
            <StatCard
              label="Errors"
              value={result.error_count_total}
              tone={result.error_count_total > 0 ? "negative" : "positive"}
            />
            <StatCard label="Rows dropped" value={result.rows_dropped} />
            <StatCard label="Output rows" value={result.output_rows} />
          </div>
          {result.rules.map((rule, index) => (
            <RuleResultCard key={index} rule={rule} />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * The visible text is the raw keystrokes; the parsed list is derived
 * alongside it so typing a trailing comma is not clobbered by re-renders.
 */
function AllowedValuesInput({
  values,
  onChange,
}: {
  values: string[];
  onChange: (values: string[]) => void;
}) {
  const [raw, setRaw] = useState(values.join(","));
  return (
    <input
      type="text"
      aria-label="Allowed values (comma separated)"
      placeholder="active,inactive"
      style={{ width: 260 }}
      value={raw}
      onChange={(event) => {
        setRaw(event.target.value);
        onChange(event.target.value.split(",").map((v) => v.trim()).filter(Boolean));
      }}
    />
  );
}

function RuleResultCard({ rule }: { rule: RuleResult }) {
  return (
    <div className="card card-pad" style={{ marginBottom: 12 }}>
      <h3 style={{ marginTop: 0, display: "flex", gap: 10, alignItems: "center" }}>
        <span className="mono">{rule.column}</span>
        <span className="badge warn">{rule.rule}</span>
        <span className={`badge ${rule.passed ? "ok" : "fail"}`}>
          {rule.passed ? "passed" : `${rule.error_count} error(s)`}
        </span>
      </h3>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>
        {rule.total_values} non-null values checked · error rate{" "}
        {(rule.error_rate * 100).toFixed(1)}%
      </p>
      {rule.samples.length > 0 && (
        <div className="table-wrap mt">
          <table className="data">
            <thead>
              <tr>
                <th>Row</th>
                <th>Value</th>
                <th>Problem</th>
              </tr>
            </thead>
            <tbody>
              {rule.samples.map((sample, index) => (
                <tr key={index}>
                  <td>{sample.row}</td>
                  <td className="mono">{sample.value ?? "(null)"}</td>
                  <td>{sample.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
