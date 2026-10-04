from pathlib import Path
import pytest
from src.analytics import load_inputs, prepare_data
from src.modeling import train_reason_model

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture(scope="session")
def project_root():
    return ROOT

@pytest.fixture(scope="session")
def inputs():
    return load_inputs(ROOT / "data" / "raw")

@pytest.fixture(scope="session")
def results(inputs):
    return prepare_data(inputs, legacy_divisor=100.0)

@pytest.fixture(scope="session")
def trained_model(results):
    return train_reason_model(results["canonical"])
