import argparse
import json
from pathlib import Path

import pandas as pd
from xgboost import XGBRegressor


FEATURES = ["Crop", "Season", "State", "Area", "Annual_Rainfall", "Fertilizer", "Pesticide"]


def load_yield_data(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = set(FEATURES + ["Yield"]).difference(frame.columns)
    if missing:
        raise ValueError(f"Yield dataset missing columns: {sorted(missing)}")
    return frame


def cold_start_weight(history_count: int) -> float:
    import math
    return 1 / (1 + math.exp(-0.15 * (history_count - 30)))


def train(input_path: str | Path, output_path: str | Path):
    frame = load_yield_data(input_path).copy()
    encoded = pd.get_dummies(frame[FEATURES], columns=["Crop", "Season", "State"])
    model = XGBRegressor(n_estimators=300, max_depth=6, learning_rate=0.05, objective="reg:squarederror", n_jobs=2)
    model.fit(encoded, frame["Yield"])
    artifact = {"model": model.get_booster().save_raw().hex(), "features": list(encoded.columns), "cold_start_formula": "1/(1+exp(-0.15*(N-30)))"}
    Path(output_path).write_text(json.dumps(artifact), encoding="utf-8")
    return model, encoded.columns.tolist()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="archive/crop_yield.csv")
    parser.add_argument("--output", default="ml/models/yield_regressor_v1.json")
    arguments = parser.parse_args()
    Path(arguments.output).parent.mkdir(parents=True, exist_ok=True)
    train(arguments.input, arguments.output)
