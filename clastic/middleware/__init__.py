# -*- coding: utf-8 -*-

from .core import (Middleware,
                   check_middlewares,
                   merge_middlewares,
                   make_middleware_chain,
                   DummyMiddleware,
                   ContextProcessor,
                   SimpleContextProcessor)


from .url import GetParamMiddleware