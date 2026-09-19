from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    status: str
    database: str
    # Only meaningful when RESUME_STORAGE_PROVIDER=mongodb_gridfs — omitted
    # (None) when resume storage is "local", since readiness must not
    # depend on a dependency that configuration says isn't in use.
    mongodb: str | None = None
