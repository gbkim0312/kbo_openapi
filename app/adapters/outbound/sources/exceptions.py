class SourceError(Exception):
    pass


class SourceTransportError(SourceError):
    pass


class SourceSchemaChangedError(SourceError):
    pass


class SourceNoGames(SourceError):
    pass


class SourceConfigurationError(SourceError):
    pass
