from src.modeling import predict_reason


def test_ai_model_has_disclosed_holdout_metrics_and_returns_suggestions(trained_model):
    metrics = trained_model["metrics"]
    assert metrics["n_labelled"] == 2340
    assert metrics["n_test"] == 585
    assert metrics["random_state"] == 42
    assert 0.40 <= metrics["accuracy"] <= 0.75
    assert 0.40 <= metrics["macro_f1"] <= 0.75
    assert len(trained_model["holdout"]) == metrics["n_test"]
    suggestion = predict_reason(trained_model["model"], "Card payment was debited twice but I received no order confirmation.")
    assert len(suggestion) == 3
    assert suggestion.iloc[0].suggested_reason_code == "DUP-PAYMENT"
    assert suggestion.iloc[:, 1].between(0, 1).all()
