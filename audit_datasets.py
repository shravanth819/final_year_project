import os
import sys
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')
base = r'D:\FINALPROJECT'

print('ORIGINAL DATASETS ONLY')
print('-' * 50)

print('[1] SOIL CLASSIFIER (FR-01) - MobileNetV2')
for ds in ['CyAUG-Dataset', 'Orignal-Dataset']:
    ds_path = os.path.join(base, 'archive', ds)
    classes = {}
    for cls in sorted(os.listdir(ds_path)):
        cls_path = os.path.join(ds_path, cls)
        if os.path.isdir(cls_path):
            classes[cls] = len(os.listdir(cls_path))
    role = 'TRAIN' if 'CyAUG' in ds else 'TEST'
    print(f'  [{role}] {ds}: {sum(classes.values())} images')
    for k, v in classes.items():
        print(f'         {k}: {v}')

print()
print('[2] DISEASE CLASSIFIER - MobileNetV2 (PlantVillage)')
pv = os.path.join(base, 'archive', 'PlantVillage')
total_pv = 0
for cls in sorted(os.listdir(pv)):
    cls_path = os.path.join(pv, cls)
    if os.path.isdir(cls_path):
        cnt = len([f for f in os.listdir(cls_path) if os.path.isfile(os.path.join(cls_path, f))])
        if cnt > 0:
            total_pv += cnt
            print(f'  {cls}: {cnt}')
print(f'  TOTAL: {total_pv} images')

print()
print('[3] YIELD REGRESSOR (FR-04) - XGBoost')
df_y = pd.read_csv(os.path.join(base, 'archive', 'crop_yield.csv'))
print('  File: crop_yield.csv')
print('  Shape:', df_y.shape)
print('  Columns:', list(df_y.columns))
print('  Unique Crops:', df_y['Crop'].nunique())
print('  Unique States:', df_y['State'].nunique())
print('  Year Range:', int(df_y['Crop_Year'].min()), '-', int(df_y['Crop_Year'].max()))

print()
print('[4] CROP RECOMMENDER + COLD-START RULES (FR-04)')
df_r = pd.read_excel(os.path.join(base, 'archive', 'Crop Recommendation Dataset.xlsx'))
print('  File: Crop Recommendation Dataset.xlsx')
print('  Shape:', df_r.shape)
print('  Columns:', list(df_r.columns))
print('  NOTE: Temperature/Humidity/pH/Rainfall only (no N/P/K columns)')
print('  Unique crops:', df_r['Label'].nunique())

print()
print('[5] RAG KNOWLEDGE BASE (FR-05) - Real FAO PDFs')
rag = os.path.join(base, 'rag_docs')
if os.path.exists(rag):
    for f in sorted(os.listdir(rag)):
        kb = round(os.path.getsize(os.path.join(rag, f)) / 1024)
        print('  ' + f + ' (' + str(kb) + ' KB)')
else:
    print('  No rag_docs/ present')
