"""
Pydantic v2 models for dbt manifest and run results structures.

dbt 1.5+ uses manifest v10 schema. Older projects might be v9 or earlier — we're
lenient on extra fields via extra='ignore' so we don't blow up on unknown keys.

Reference: https://schemas.getdbt.com/dbt/manifest/v10/manifest.json
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DbtColumn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    description: str = ""
    data_type: Optional[str] = None


class DbtNodeConfig(BaseModel):
    # populate_by_name=True lets callers use 'schema_' directly after our remap
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    materialized: Optional[str] = None
    schema_: Optional[str] = None  # 'schema' is a Pydantic reserved keyword
    tags: list[str] = []
    enabled: bool = True

    @classmethod
    def model_validate(cls, obj: object, **kwargs):  # type: ignore[override]
        # Remap 'schema' -> 'schema_' before validation so callers don't have to
        if isinstance(obj, dict) and "schema" in obj and "schema_" not in obj:
            obj = {**obj, "schema_": obj.pop("schema")}
        return super().model_validate(obj, **kwargs)


class DbtNodeDependsOn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    nodes: list[str] = []
    macros: list[str] = []


class DbtManifestNode(BaseModel):
    """Represents a model, test, seed, snapshot, or analysis node in the manifest."""

    model_config = ConfigDict(extra="ignore")

    unique_id: str
    fqn: list[str] = []
    name: str
    resource_type: str
    original_file_path: str = ""
    description: str = ""
    columns: dict[str, DbtColumn] = {}
    config: DbtNodeConfig = DbtNodeConfig()
    depends_on: DbtNodeDependsOn = DbtNodeDependsOn()
    raw_code: Optional[str] = None
    compiled_code: Optional[str] = None
    tags: list[str] = []
    # Some manifest versions store these at the node level
    schema_: Optional[str] = None
    database: Optional[str] = None
    package_name: Optional[str] = None

    @classmethod
    def model_validate(cls, obj: object, **kwargs):  # type: ignore[override]
        if isinstance(obj, dict) and "schema" in obj and "schema_" not in obj:
            obj = {**obj, "schema_": obj.pop("schema")}
        return super().model_validate(obj, **kwargs)


class DbtSource(BaseModel):
    """Source nodes live under manifest['sources'], not manifest['nodes']."""

    model_config = ConfigDict(extra="ignore")

    unique_id: str
    name: str
    source_name: str = ""
    identifier: str = ""
    loader: str = ""
    schema_: Optional[str] = None
    database: Optional[str] = None
    description: str = ""
    columns: dict[str, DbtColumn] = {}
    tags: list[str] = []
    depends_on: DbtNodeDependsOn = DbtNodeDependsOn()

    @classmethod
    def model_validate(cls, obj: object, **kwargs):  # type: ignore[override]
        if isinstance(obj, dict) and "schema" in obj and "schema_" not in obj:
            obj = {**obj, "schema_": obj.pop("schema")}
        return super().model_validate(obj, **kwargs)


class DbtExposure(BaseModel):
    """Downstream consumers of dbt models — dashboards, ML models, etc."""

    model_config = ConfigDict(extra="ignore")

    unique_id: str
    name: str
    type: str = ""
    label: str = ""
    description: str = ""
    depends_on: DbtNodeDependsOn = DbtNodeDependsOn()
    tags: list[str] = []


class DbtManifest(BaseModel):
    """Top-level manifest.json structure."""

    model_config = ConfigDict(extra="ignore")

    metadata: dict = {}
    nodes: dict[str, DbtManifestNode] = {}
    sources: dict[str, DbtSource] = {}
    exposures: dict[str, DbtExposure] = {}
    # parent_map and child_map are present in dbt >= 1.0 manifests
    parent_map: Optional[dict[str, list[str]]] = None
    child_map: Optional[dict[str, list[str]]] = None


# ---------------------------------------------------------------------------
# Run Results
# ---------------------------------------------------------------------------


class RunResultStatus(str, Enum):
    success = "success"
    error = "error"
    warn = "warn"
    skipped = "skipped"
    pass_ = "pass"
    fail = "fail"

    # dbt sometimes emits these in older adapters
    runtime_error = "runtime error"

    @classmethod
    def _missing_(cls, value: object) -> "RunResultStatus":
        # Gracefully handle unknown statuses by mapping them to error
        return cls.error


class DbtRunResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    unique_id: str
    status: RunResultStatus
    execution_time: float = 0.0
    message: Optional[str] = None
    failures: Optional[int] = None
    thread_id: str = ""
    timing: list[dict] = []


class DbtRunResults(BaseModel):
    model_config = ConfigDict(extra="ignore")

    metadata: dict = {}
    results: list[DbtRunResult] = []
    elapsed_time: float = 0.0
