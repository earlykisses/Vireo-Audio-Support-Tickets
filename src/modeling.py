"""Local, reproducible TF-IDF + logistic-regression reason-code suggestion model.

The model learns the existing agent-selected reason code, which is an imperfect target.
Predictions are suggestions only and must not overwrite the original reason code.
"""
from __future__ import annotations
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import Pipeline


def _model() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=20000, sublinear_tf=True)),
        ("classifier", OneVsRestClassifier(LogisticRegression(max_iter=300, solver="liblinear", class_weight="balanced", C=2.0, random_state=42))),
    ])


def train_reason_model(canonical: pd.DataFrame) -> dict:
    """Train/evaluate on an 75/25 stratified split, then fit a final local suggestion model."""
    usable = canonical[(canonical.refund_amount_normalized_inr.fillna(0) > 0) &
                       canonical.refund_reason_code.notna() &
                       canonical.refund_reason_code.ne("UNCODED")].copy()
    usable["model_text"] = (usable.customer_message.fillna("").astype(str) + " " +
                            usable.agent_notes.fillna("").astype(str)).str.strip()
    usable = usable[usable.model_text.str.len() > 0]
    if usable.refund_reason_code.nunique() < 2 or len(usable) < 40:
        raise ValueError("Not enough labelled refund records to evaluate the local reason-code model.")
    X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
        usable.model_text, usable.refund_reason_code, usable.index,
        test_size=0.25, random_state=42, stratify=usable.refund_reason_code
    )
    holdout_model = _model()
    holdout_model.fit(X_train, y_train)
    predictions = holdout_model.predict(X_test)
    probabilities = holdout_model.predict_proba(X_test)
    confidence = probabilities.max(axis=1)
    labels = sorted(usable.refund_reason_code.unique())
    report_dict = classification_report(y_test, predictions, labels=labels, output_dict=True, zero_division=0)
    report = pd.DataFrame(report_dict).T.reset_index(names="class_or_metric")
    matrix = pd.DataFrame(confusion_matrix(y_test, predictions, labels=labels), index=labels, columns=labels)
    holdout = pd.DataFrame({
        "ticket_id": canonical.loc[idx_test, "ticket_id"].astype(str).values,
        "refund_month": canonical.loc[idx_test, "refund_month"].astype(str).values,
        "agent_id": canonical.loc[idx_test, "agent_id"].astype(str).values,
        "actual_reason_code": y_test.astype(str).values,
        "suggested_reason_code": predictions.astype(str),
        "confidence": confidence,
        "correct": predictions == y_test.to_numpy(),
        "refund_amount_inr": canonical.loc[idx_test, "refund_amount_normalized_inr"].values,
        "model_text": usable.loc[idx_test, "model_text"].values,
    }).sort_values(["correct", "confidence"], ascending=[True, False])
    final_model = _model()
    final_model.fit(usable.model_text, usable.refund_reason_code)
    return {
        "model": final_model,
        "holdout_model": holdout_model,
        "holdout": holdout,
        "class_report": report,
        "confusion_matrix": matrix,
        "metrics": {
            "n_labelled": int(len(usable)),
            "n_train": int(len(X_train)),
            "n_test": int(len(X_test)),
            "accuracy": float(accuracy_score(y_test, predictions)),
            "macro_f1": float(f1_score(y_test, predictions, average="macro")),
            "weighted_f1": float(f1_score(y_test, predictions, average="weighted")),
            "random_state": 42,
            "test_size": 0.25,
        },
    }


def predict_reason(model: Pipeline, text: str) -> pd.DataFrame:
    text = (text or "").strip()
    if not text:
        raise ValueError("Enter a customer message or agent note first.")
    probabilities = model.predict_proba([text])[0]
    classes = model.named_steps["classifier"].classes_
    ranking = sorted(zip(classes, probabilities), key=lambda item: item[1], reverse=True)[:3]
    return pd.DataFrame(ranking, columns=["suggested_reason_code", "model_score"])
