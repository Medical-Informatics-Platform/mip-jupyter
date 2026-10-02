import sys
from unittest.mock import MagicMock

print("Importing mip...", flush=True)
try:
    import mip
    from mip.filters import F
    from mip.preprocessing import MissingValuesHandler
except Exception as exc:
    print(f"Import failed: {exc}", flush=True)
    sys.exit(1)
print("Import successful.", flush=True)

MOCK_DATA_MODELS = [
    {
        "code": "dementia",
        "version": "0.1",
        "label": "Dementia",
        "longitudinal": False,
        "variables": [],
        "groups": [
            {
                "code": "clinical",
                "label": "Clinical",
                "variables": [
                    {"code": "age", "label": "Age", "type": "real"},
                    {"code": "mmse", "label": "MMSE", "type": "integer"},
                    {"code": "diagnosis", "label": "Diagnosis", "type": "nominal"},
                ],
            }
        ],
        "datasets": [{"code": "adni", "label": "ADNI"}],
        "datasetsVariables": {"adni": ["age", "mmse", "diagnosis"]},
    }
]

transport = MagicMock()
transport.get.return_value = MOCK_DATA_MODELS
transport.post.return_value = {"status": "success", "result": {"bins": [1, 2], "counts": [3, 4]}}

client = mip.Client("http://mock-backend/services")
client._transport = transport

print("Testing catalog path...", flush=True)
dm = client.catalog().data_model("Dementia")
adni = dm.datasets["ADNI"]
age = dm.variables["Age"]
mmse = dm.variables["MMSE"]
if dm.name != "Dementia (0.1)" or not adni.has_variable(mmse):
    print("Catalog smoke test FAILED", flush=True)
    sys.exit(1)
print("Catalog smoke test PASSED", flush=True)

print("Testing pipeline path...", flush=True)
analysis_set = mip.AnalysisSet(data_model=dm, datasets=[adni], variables=[age, mmse])
pipeline = mip.Pipeline(
    analysis_set=analysis_set,
    filters=F(age) >= 50,
    handle_missing=MissingValuesHandler(strategies={mmse: "mean"}),
)
result = pipeline.histogram(variable=mmse, bins=20)
if result.raw != {"bins": [1, 2], "counts": [3, 4]}:
    print("Pipeline smoke test FAILED", flush=True)
    sys.exit(1)
print("Pipeline smoke test PASSED", flush=True)
