import argparse
from pathlib import Path

import pandas as pd
from xgboost import XGBClassifier


FEATURES = ["n_slope", "p_slope", "k_slope", "rainfall_trend", "fertilizer_days_since"]


def build_features(history: pd.DataFrame) -> pd.DataFrame:
    missing = set(FEATURES + ["risk_label"]).difference(history.columns)
    if missing:
        raise ValueError(f"Soil health history requires labeled fields: {sorted(missing)}")
    return history[FEATURES].fillna(0)


def train(input_path: str | Path, output_path: str | Path):
    frame = pd.read_csv(input_path)
    features = build_features(frame)
    model = XGBClassifier(n_estimators=150, max_depth=4, learning_rate=0.08, objective="multi:softprob", eval_metric="mlogloss", n_jobs=2)
    model.fit(features, frame["risk_label"])
    model.save_model(output_path)
    return model


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train from labeled rolling sensor history; no synthetic labels are generated")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="ml/models/soil_health_clf_v1.json")
    arguments = parser.parse_args()
    Path(arguments.output).parent.mkdir(parents=True, exist_ok=True)
    train(arguments.input, arguments.output)
