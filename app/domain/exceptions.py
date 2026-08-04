class DomainError(Exception):
    code = "INTERNAL_ERROR"
    message = "서버 내부 오류가 발생했습니다."
    status_code = 500


class GameNotFoundError(DomainError):
    code, message, status_code = "GAME_NOT_FOUND", "경기를 찾을 수 없습니다.", 404


class CollectionInProgressError(DomainError):
    code, message, status_code = "COLLECTION_IN_PROGRESS", "이미 수집이 진행 중입니다.", 409


class SourceUnavailableError(DomainError):
    code, message, status_code = "SOURCE_UNAVAILABLE", "데이터 원본을 사용할 수 없습니다.", 503
