from app.core.inference.base import ColumnSample
from app.core.inference.heuristics import HeuristicInferenceProvider

TARGETS = ["customer_name", "email", "phone", "created_at", "customer_id", "city"]


def suggest(*names: str, targets=TARGETS):
    provider = HeuristicInferenceProvider()
    columns = [ColumnSample(name=n, sample_values=["x"]) for n in names]
    return {s.source: s for s in provider.suggest(columns, targets)}


class TestHeuristicInference:
    def test_demo_mapping_case(self):
        """The canonical portfolio demo: cust_nm / mail / ph_no."""
        suggestions = suggest("cust_nm", "mail", "ph_no")
        assert suggestions["cust_nm"].target == "customer_name"
        assert suggestions["mail"].target == "email"
        assert suggestions["ph_no"].target == "phone"

    def test_exact_match(self):
        assert suggest("email")["email"].target == "email"
        assert suggest("email")["email"].confidence == 1.0

    def test_case_and_separators_normalized(self):
        assert suggest("Customer Name")["Customer Name"].target == "customer_name"
        assert suggest("E-Mail")["E-Mail"].target == "email"

    def test_unknown_column_has_no_suggestion(self):
        suggestions = suggest("zzz_qqq_flurb")
        assert "zzz_qqq_flurb" not in suggestions

    def test_confidence_within_bounds(self):
        for suggestion in suggest("cust_nm", "mail", "ph_no", "email", "phone", "xyz").values():
            assert 0.0 <= suggestion.confidence <= 1.0

    def test_rationale_present(self):
        assert suggest("mail")["mail"].rationale

    def test_deterministic(self):
        first = suggest("cust_nm", "mail", "ph_no", "reg_dttm")
        second = suggest("cust_nm", "mail", "ph_no", "reg_dttm")
        assert {k: v.target for k, v in first.items()} == {k: v.target for k, v in second.items()}

    def test_custom_targets(self):
        suggestions = suggest("mail", targets=["email_address"])
        assert suggestions["mail"].target == "email_address"
