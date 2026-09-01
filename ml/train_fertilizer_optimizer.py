import argparse
import json
from pathlib import Path

import pandas as pd
from xgboost import XGBRegressor


def train(input_path: str | Path, output_path: str | Path):
    frame = pd.read_csv(input_path)
    required = {"Fertilizer", "Pesticide", "Yield", "Area"}
    if missing := required.difference(frame.columns):
        raise ValueError(f"Fertilizer training data missing columns: {sorted(missing)}")
    features = frame[["Area", "Pesticide"]].fillna(0)
    models = {}
    for nutrient, target in (("n", "Fertilizer"), ("p", "Pesticide"), ("k", "Yield")):
        model = XGBRegressor(n_estimators=120, max_depth=4, learning_rate=0.08, objective="reg:squarederror", n_jobs=2)
        model.fit(features, frame[target])
        models[nutrient] = model.get_booster().save_raw().hex()
    artifact = {"models": models, "features": list(features.columns), "safe_limit_multiplier": 1.2, "source": str(input_path)}
    Path(output_path).write_text(json.dumps(artifact), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="archive/crop_yield.csv")
    parser.add_argument("--output", default="ml/models/fertilizer_optimizer_v1.json")
    arguments = parser.parse_args()
    Path(arguments.output).parent.mkdir(parents=True, exist_ok=True)
    train(arguments.input, arguments.output)
