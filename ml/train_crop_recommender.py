import argparse
import json
from pathlib import Path

import pandas as pd
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

try:
    from .crop_recommender import apply_rotation_filter, build_feature_vector
except ImportError:
    from crop_recommender import apply_rotation_filter, build_feature_vector


def load_dataset(path: str | Path) -> pd.DataFrame:
    frame = pd.read_excel(path)
    required = {"Temperature", "Humidity", "pH", "Rainfall", "Label"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Crop recommendation dataset missing columns: {sorted(missing)}")
    return frame


def train(input_path: str | Path, output_path: str | Path):
    frame = load_dataset(input_path)
    features = frame[["Temperature", "Humidity", "pH", "Rainfall"]]
    labels = LabelEncoder().fit_transform(frame["Label"])
    model = XGBClassifier(n_estimators=150, max_depth=5, learning_rate=0.08, objective="multi:softprob", eval_metric="mlogloss", n_jobs=2)
    model.fit(features, labels)
    artifact = {"model": model.get_booster().save_raw().hex(), "features": list(features.columns), "classes": sorted(frame["Label"].unique().tolist()), "cold_start": True, "rotation_filter": "two-season family gap"}
    Path(output_path).write_text(json.dumps(artifact), encoding="utf-8")
    return model


def recommend(model, frame: pd.DataFrame, sensor: dict, previous_crop: str | None = None, seasons_since_previous: int = 99, history: dict | None = None, static: dict | None = None, top_k: int = 3):
    vector = build_feature_vector(sensor, history, static)
    features = [[sensor.get("temperature", 0), sensor.get("humidity", 0), sensor.get("ph", 0), sensor.get("rainfall", 0)]]
    probabilities = model.predict_proba(features)[0]
    classes = model.classes_
    label_names = sorted(frame["Label"].unique().tolist())
    ranked = [label_names[int(classes[index])] for index in probabilities.argsort()[::-1]]
    accepted, filtered = apply_rotation_filter(ranked, previous_crop, seasons_since_previous)
    confidence_by_label = {label_names[int(classes[index])]: float(probabilities[index]) for index in range(len(classes))}
    return {"recommendations": [{"crop": crop, "confidence": round(confidence_by_label.get(crop, 0), 4)} for crop in accepted[:top_k]], "filtered": [item.__dict__ for item in filtered], "cold_start": vector["cold_start"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="archive/Crop Recommendation Dataset.xlsx")
    parser.add_argument("--output", default="ml/models/crop_recommender_v1.json")
    arguments = parser.parse_args()
    Path(arguments.output).parent.mkdir(parents=True, exist_ok=True)
    train(arguments.input, arguments.output)
