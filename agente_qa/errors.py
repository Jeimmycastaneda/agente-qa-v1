"""Errores de dominio para la arquitectura modular."""

class AgenteQAError(RuntimeError):
    def __init__(self, user_message, detail=""):
        super().__init__(user_message)
        self.user_message = user_message
        self.detail = detail

class ConfigError(AgenteQAError):
    pass

class SourceError(AgenteQAError):
    pass

class QuotaError(AgenteQAError):
    pass
