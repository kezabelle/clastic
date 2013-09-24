# -*- coding: utf-8 -*-

"""
One notable (if incremental) improvement over Werkzeug's error system
is that 400-level requests share a common base class
(BadRequest). Same goes for do 500-coded requests
(InternalServerError).
"""

"""
Clastic HTTP exceptions seek to provide a general structure for errors
that readily translates to common human- and machine-readable formats
(i.e., JSON, XML, HTML, plain text). It does so with the following
fields:

- code (required): Defines the fundamental class of error, as
  according to the HTTP spec, usually implied by the HTTPException
  subclass being used
- message: A short message describing the error, defaulting to
  the one specified by HTTP (e.g., 403 -> "Forbidden",
  404 -> "Not Found")
- detail: A longer-form description of the message, used as
  the body of the response. Could include an explanation of the error,
  trace information, or unique identifiers. Structured values
  will be JSON-ified.
- error_type: A short value specifying the specific subtype of HTTP
  (e.g., for 403, "http://example.net/errors/invalid_token")

TODO: naming scheme?
TODO: HTTPException could well be a metaclass
TODO: enable detail to be a templatable thing?
"""

from werkzeug.wrappers import BaseResponse


class HTTPException(BaseResponse, Exception):
    code = None
    message = 'Error'
    detail = 'An unspecified error occurred.'

    def __init__(self, detail=None, **kwargs):
        # TODO: could be streamed
        self.detail = detail or self.detail
        self.error_type = kwargs.pop('error_type', None)
        self.message = kwargs.pop('message', self.message)
        self.code = kwargs.pop('code', self.code)
        self.is_breaking = kwargs.pop('is_breaking', True)

        headers = kwargs.pop('headers', None)
        mimetype = kwargs.pop('mimetype', None)
        content_type = kwargs.pop('content_type', None)
        super(HTTPException, self).__init__(response=self.detail,
                                            status=self.code,
                                            headers=headers,
                                            mimetype=mimetype,
                                            content_type=content_type)


class BadRequest(HTTPException):
    code = 400


class Unauthorized(BadRequest):
    code = 401


class PaymentRequired(BadRequest):
    "HTTP cares about your paywall."
    code = 402


class Forbidden(BadRequest):
    code = 403


class NotFound(BadRequest):
    code = 404


class MethodNotAllowed(BadRequest):
    code = 405


class NotAcceptable(BadRequest):
    code = 406


class ProxyAuthenticationRequired(BadRequest):
    code = 407


class RequestTimeout(BadRequest):
    code = 408


class Conflict(BadRequest):
    code = 409


class Gone(BadRequest):
    code = 410


class LengthRequired(BadRequest):
    code = 411


class PreconditionFailed(BadRequest):
    code = 412


class RequestEntityTooLarge(BadRequest):
    "more like ErrorNameTooLong, amirite?"
    code = 413


class RequestURITooLong(BadRequest):
    "... shit."
    code = 414


class UnsupportedMediaType(BadRequest):
    code = 415


class RequestedRangeNotSatisfiable(BadRequest):
    code = 416


class ExpectationFailed(BadRequest):
    "Can't. always. get. what you want."
    code = 417


class InternalServerError(HTTPException):
    code = 500


class NotImplemented(InternalServerError):
    code = 501


class BadGateway(InternalServerError):
    code = 502


class ServiceUnavailable(InternalServerError):
    code = 503


class GatewayTimeout(InternalServerError):
    code = 504


class HTTPVersionNotSupported(InternalServerError):
    code = 505


if __name__ == '__main__':
    print GatewayTimeout()
