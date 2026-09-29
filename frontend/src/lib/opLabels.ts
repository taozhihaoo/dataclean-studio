/** Human labels for normalization operations (shared by pipeline UI). */

import type { NormalizationOp } from "../types";

export const OP_LABELS: Record<NormalizationOp, string> = {
  trim: "Trim whitespace",
  collapse_spaces: "Collapse spaces",
  lowercase: "lowercase",
  uppercase: "UPPERCASE",
  title_case: "Title Case",
  empty_to_null: "Empty → null",
  null_tokens_to_null: "NULL/N/A → null",
  normalize_date: "Normalize dates",
  normalize_phone: "Normalize phones",
};
