"""Frozen fixture records and explicit tool schemas."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

SNAPSHOT_ID = "DEMO-2026-09-15-A"
CLOCK = "2026-09-15T10:00:00Z"
EmployeeID = Annotated[str, Field(pattern=r"^E[0-9]{4}$")]
ServiceID = Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")]
IncidentID = Annotated[str, Field(pattern=r"^INC-(?:LIVE-[0-9]{4}|[0-9]{4}-[0-9]{3})$")]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Record(FrozenModel):
    record_id: str
    snapshot_id: Literal["DEMO-2026-09-15-A"]
    updated_at: AwareDatetime


class Employee(Record):
    employee_id: EmployeeID
    name: str
    title: str
    team_id: ServiceID
    manager_id: EmployeeID | None
    active: bool
    email: Annotated[str, Field(pattern=r"^[a-z.]+@northstar\.example$")]


class Team(Record):
    team_id: ServiceID
    name: str
    manager_employee_id: EmployeeID


class Responsibility(FrozenModel):
    responsibility_id: ServiceID
    employee_id: EmployeeID
    description: str
    basis_document_ids: tuple[str, ...]


class Service(Record):
    service_id: ServiceID
    name: str
    domain: Literal["payments", "platform", "risk", "identity", "finance"]
    owner_team_id: ServiceID
    tier: Literal[1, 2]
    dependencies: tuple[ServiceID, ...]
    oncall_rotation_id: ServiceID
    responsibilities: tuple[Responsibility, ...]


class Shift(Record):
    shift_id: str
    service_id: ServiceID
    rotation_id: ServiceID
    employee_id: EmployeeID
    level: Literal["primary"]
    starts_at: AwareDatetime
    ends_at: AwareDatetime


class Incident(Record):
    incident_id: IncidentID
    service_id: ServiceID
    severity: Literal["SEV-1", "SEV-2"]
    status: Literal["investigating", "mitigating", "monitoring"]
    symptoms: tuple[str, ...]
    commander_employee_id: EmployeeID
    started_at: AwareDatetime
    confirmed_root_cause: None


class Deployment(Record):
    deployment_id: str
    service_id: ServiceID
    version: str
    deployed_at: AwareDatetime
    change_id: Annotated[str, Field(pattern=r"^CHG-[0-9]{3}$")]
    environment: Literal["production"]
    model_release_id: str | None
    configuration_version: str | None


class FileSpec(FrozenModel):
    filename: str
    count: int
    sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class Manifest(FrozenModel):
    snapshot_id: Literal["DEMO-2026-09-15-A"]
    as_of: Literal["2026-09-15T10:00:00Z"]
    schema_version: Literal[1]
    horizon_start: AwareDatetime
    horizon_end: AwareDatetime
    files: dict[str, FileSpec]
    source_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EmployeeArgs(Arguments):
    employee_id: EmployeeID


class ServiceArgs(Arguments):
    service_id: ServiceID


class IncidentArgs(Arguments):
    incident_id: IncidentID


class OncallArgs(ServiceArgs):
    at: str | None = None


class OpenIncidentArgs(Arguments):
    service_id: ServiceID | None = None


class SearchArgs(Arguments):
    query: Annotated[str, Field(min_length=1, max_length=80)]
    team_id: ServiceID | None = None

    @field_validator("query")
    @classmethod
    def meaningful_query(cls, value):
        value = value.strip()
        if not any(char.isalnum() for char in value):
            raise ValueError("query must contain a letter or number")
        return value


class EmployeeMatch(FrozenModel):
    record_id: str
    employee_id: EmployeeID
    name: str
    title: str
    team_id: ServiceID
    active: Literal[True]
    updated_at: AwareDatetime


class EmployeeMatches(FrozenModel):
    items: tuple[EmployeeMatch, ...]
    total_matches: int
    truncated: bool


class ServiceDetails(FrozenModel):
    service: Service
    owner_team: Team


class OncallDetails(FrozenModel):
    queried_at: AwareDatetime
    shift: Shift


class IncidentSummary(FrozenModel):
    record_id: str
    incident_id: IncidentID
    service_id: ServiceID
    severity: str
    status: str
    updated_at: AwareDatetime


class OpenIncidents(FrozenModel):
    items: tuple[IncidentSummary, ...]


class Response[T](FrozenModel):
    snapshot_id: Literal["DEMO-2026-09-15-A"] = SNAPSHOT_ID
    as_of: Literal["2026-09-15T10:00:00Z"] = CLOCK
    source: str
    record_id: str
    payload: T
