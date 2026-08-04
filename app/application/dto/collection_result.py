from dataclasses import dataclass
from uuid import UUID

from app.domain.enums.collection_status import CollectionStatus


@dataclass(frozen=True, slots=True)
class CollectionResult:
    job_id: UUID
    status: CollectionStatus
    fetched_count: int
    inserted_count: int
    updated_count: int
    unchanged_count: int
    failed_count: int
