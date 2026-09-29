"""Deterministic heuristic column-mapping inference.

Pure string similarity against a curated synonym table — no network, no
API key, fully offline and reproducible. This is the default (and only
required) provider.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from app.core.inference.base import ColumnSample, MappingSuggestion

SYNONYMS: dict[str, list[str]] = {
    "customer_id": ["cust_id", "customerid", "id", "client_id", "customer_no", "custno"],
    "customer_name": [
        "cust_nm",
        "custnm",
        "name",
        "fullname",
        "client_name",
        "cust_name",
        "customername",
    ],
    "email": ["mail", "e_mail", "email_address", "mail_address", "emailaddress", "contact_email"],
    "phone": [
        "ph_no",
        "phno",
        "tel",
        "telephone",
        "mobile",
        "phone_number",
        "ph",
        "contact_number",
    ],
    "age": ["years", "customer_age", "alter"],
    "status": ["state", "customer_status", "active_flag"],
    "created_at": [
        "created",
        "createdate",
        "creation_date",
        "registered_at",
        "signup_date",
        "date_joined",
    ],
    "city": ["town", "location", "city_name"],
    "amount": ["total", "sum", "value", "price", "order_amount"],
    "order_id": ["orderid", "order_no", "orderno", "purchase_id"],
    "order_date": ["date", "orderdate", "purchase_date"],
    "country": ["nation", "country_name"],
    "address": ["street", "street_address", "addr"],
    "company": ["organization", "org", "employer", "company_name"],
    "first_name": ["firstname", "given_name", "fname"],
    "last_name": ["lastname", "surname", "family_name", "lname"],
}

_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def _normalize(name: str) -> str:
    return _NORMALIZE_RE.sub("", name.strip().lower())


class HeuristicInferenceProvider:
    name = "heuristic"

    def suggest(self, columns: list[ColumnSample], targets: list[str]) -> list[MappingSuggestion]:
        target_names = [t for t in targets if t.strip()]
        suggestions: list[MappingSuggestion] = []
        for column in columns:
            best = self._best_match(column.name, target_names)
            if best:
                suggestions.append(
                    MappingSuggestion(
                        source=column.name,
                        target=best[0],
                        confidence=round(best[1], 2),
                        rationale=best[2],
                        provider=self.name,
                    )
                )
        return suggestions

    def _best_match(self, source: str, targets: list[str]) -> tuple[str, float, str] | None:
        normalized = _normalize(source)
        best: tuple[str, float, str] | None = None
        for target in targets:
            score, rationale = 0.0, ""
            synonyms = SYNONYMS.get(target, [])
            if normalized == _normalize(target):
                score, rationale = 1.0, "exact name match"
            elif normalized in [_normalize(s) for s in synonyms]:
                score, rationale = 0.95, f"known synonym of '{target}'"
            else:
                candidates = [_normalize(target)] + [_normalize(s) for s in synonyms]
                similarity = max(SequenceMatcher(None, normalized, c).ratio() for c in candidates)
                token_in = any(
                    c and (c in normalized or normalized in c) for c in candidates if len(c) >= 4
                )
                if similarity >= 0.75:
                    score, rationale = similarity * 0.9, f"name similarity {similarity:.2f}"
                elif token_in:
                    score, rationale = 0.6, "substring name match"
            if score > 0 and (best is None or score > best[1]):
                best = (target, score, rationale)
        return best if best and best[1] >= 0.6 else None
