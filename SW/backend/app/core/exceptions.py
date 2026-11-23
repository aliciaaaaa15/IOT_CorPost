class AppException(Exception):
    status_code = 400
    def __init__(self, code: str, message: str):
        self.code, self.message = code, message
        super().__init__(message)

class AuthenticationException(AppException): status_code = 401
class AuthorizationException(AppException):  status_code = 403
class NotFoundException(AppException):       status_code = 404
class ConflictException(AppException):       status_code = 409
class ValidationException (AppException):    status_code = 400
class PremiumRequiredException (AppException):       status_code = 403
class ConsentRequiredException (AppException):       status_code = 403
