from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

Key = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Substrate(Input):
    code: Key
    material_lot: Key
    material: Annotated[str, StringConstraints(min_length=1, max_length=80)]


class Device(Input):
    serial: Key
    position: Key


class Run(Input):
    code: Key
    substrate_code: Key
    design_revision: Key
    recipe_revision: Key
    printer: Key
    printed_at: AwareDatetime
    devices: Annotated[list[Device], Field(min_length=1, max_length=100)]


class Reading(Input):
    serial: Key
    measured_at: AwareDatetime
    value_nm: Annotated[float, Field(ge=0, le=1000000, allow_inf_nan=False)]
    spec_max_nm: Annotated[float, Field(gt=0, le=1000000, allow_inf_nan=False)]


class Batch(Input):
    instrument: Key
    external_id: Key
    readings: Annotated[list[Reading], Field(min_length=1, max_length=500)]

    @model_validator(mode="after")
    def distinct_readings(self):
        keys = [(r.serial, r.measured_at) for r in self.readings]
        if len(set(keys)) != len(keys):
            raise ValueError("Each serial and measurement timestamp pair must be unique within a batch.")
        return self
