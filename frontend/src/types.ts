/** Types mirroring the FastAPI response models. */

export interface ColumnProfile {
  name: string;
  detected_type: string;
  null_count: number;
  unique_count: number;
  sample_values: string[];
  invalid_count?: number | null;
}

export interface JobSummary {
  job_id: string;
  filename: string;
  source: string;
  status: string;
  row_count: number | null;
  column_count: number | null;
  created_at: string;
  updated_at: string;
}

export interface JobDetail extends JobSummary {
  size_bytes: number | null;
  is_transformed: boolean;
  columns: ColumnProfile[];
}

export type CellValue = string | null;

export interface PreviewResponse {
  columns: string[];
  rows: Record<string, CellValue>[];
  total_rows: number;
  limited: boolean;
}

export interface RuleConfig {
  column: string;
  rule:
    | "required"
    | "email"
    | "numeric_range"
    | "string_length"
    | "date"
    | "regex"
    | "allowed_values";
  min?: number | null;
  max?: number | null;
  min_length?: number | null;
  max_length?: number | null;
  pattern?: string | null;
  values?: string[] | null;
}

export interface InvalidSample {
  row: number;
  value: string | null;
  reason: string;
}

export interface RuleResult {
  column: string;
  rule: string;
  total_values: number;
  error_count: number;
  error_rate: number;
  passed: boolean;
  samples: InvalidSample[];
}

export interface ValidateResponse {
  total_rows: number;
  error_count_total: number;
  rows_dropped: number;
  passed: boolean;
  rules: RuleResult[];
  output_rows: number;
}

export type NormalizationOp =
  | "trim"
  | "collapse_spaces"
  | "lowercase"
  | "uppercase"
  | "title_case"
  | "empty_to_null"
  | "null_tokens_to_null"
  | "normalize_date"
  | "normalize_phone";

export interface ColumnOps {
  column: string;
  operations: NormalizationOp[];
}

export interface StepSample {
  row: number;
  column: string | null;
  before: string | null;
  after: string | null;
}

export interface StepReport {
  step_id: string;
  step_type: string;
  enabled: boolean;
  status: "applied" | "skipped";
  summary: string;
  input_rows: number;
  output_rows: number;
  stats: Record<string, unknown>;
  samples: StepSample[];
  removed_rows: Record<string, CellValue>[];
}

export type PipelineStep =
  | { id: string; type: "validate"; enabled: boolean; config: { rules: RuleConfig[]; drop_invalid_rows: boolean } }
  | { id: string; type: "normalize"; enabled: boolean; config: { columns: ColumnOps[]; date_format?: string; day_first?: boolean } }
  | { id: string; type: "dedupe"; enabled: boolean; config: { mode: "exact" | "columns"; columns: string[]; keep: "first" | "last" } }
  | { id: string; type: "rename"; enabled: boolean; config: { rename: Record<string, string>; drop: string[]; order: string[] } };

export interface TransformResponse {
  run_id: string;
  input_rows: number;
  output_rows: number;
  columns: string[];
  changed_cells: number;
  steps: StepReport[];
  preview: Record<string, CellValue>[];
}

export interface TransformPreviewResponse {
  input_rows: number;
  output_rows: number;
  columns: string[];
  steps: StepReport[];
  preview: Record<string, CellValue>[];
}

export interface RunSummary {
  run_id: string;
  job_id: string;
  kind: string;
  status: string;
  created_at: string;
  summary: Record<string, unknown> | null;
}

export interface FileMergeStat {
  job_id: string;
  filename: string;
  rows: number;
  columns: number;
}

export interface MergeResponse {
  job_id: string;
  filename: string;
  mode: string;
  input_files: FileMergeStat[];
  output_rows: number;
  output_columns: number;
  columns: string[];
  null_cells_filled: number;
}

export interface QualityReport {
  job_id: string;
  filename: string;
  generated_at: string;
  total_rows: number;
  total_columns: number;
  null_counts: Record<string, number>;
  null_cells_total: number;
  duplicate_rows: number;
  invalid_email_count: number;
  invalid_date_count: number;
  original_rows: number;
  rows_delta: number;
  validation: { run_id: string; at: string; summary: Record<string, unknown> } | null;
  transform: { run_id: string; at: string; summary: Record<string, unknown> } | null;
  merge: { run_id: string; at: string; summary: Record<string, unknown> } | null;
  columns: ColumnProfile[];
}

export interface MappingSuggestion {
  source: string;
  target: string;
  confidence: number;
  rationale: string;
  provider: string;
}

export interface InferMappingResponse {
  provider: string;
  suggestions: MappingSuggestion[];
  targets_used: string[];
}

export interface InferenceProviders {
  default: string;
  available: string[];
  openai_configured: boolean;
}

export interface MetaResponse {
  version: string;
  max_upload_mb: number;
  preview_row_limit: number;
  inference: InferenceProviders;
  target_schema_suggestions: string[];
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown> | null;
  };
}
