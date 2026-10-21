class AppError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message
        super().__init__(code)


class ModelError(AppError):
    def __init__(self):
        super().__init__(
            503, "model_unavailable", "O serviço de IA está temporariamente indisponível."
        )
