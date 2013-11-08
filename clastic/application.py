# -*- coding: utf-8 -*-

import os
import sys
from collections import Sequence
from argparse import ArgumentParser

from werkzeug.utils import redirect
from werkzeug.wrappers import (Request,
                               Response,
                               BaseResponse)
from .server import run_simple
from .route import (BaseRoute,
                    Route,
                    NullRoute,
                    normalize_path,
                    S_REDIRECT,
                    S_REWRITE,
                    S_STRICT,
                    RESERVED_ARGS)
from .tbutils import ExceptionInfo
from .middleware import check_middlewares
from .errors import (NotFound,
                     MethodNotAllowed,
                     InternalServerError)


def cast_to_route_factory(in_arg):
    if isinstance(in_arg, BaseRoute):
        return in_arg
    elif isinstance(in_arg, Sequence):
        try:
            if isinstance(in_arg[1], BaseApplication):
                return SubApplication(*in_arg)
            if callable(in_arg[1]):
                return Route(*in_arg)
        except TypeError:
            pass
    raise TypeError('Could not create routes from %r' % in_arg)


class BaseApplication(object):
    request_type = Request
    response_type = Response

    def __init__(self, routes=None, resources=None, render_factory=None,
                 middlewares=None, **kwargs):
        self.debug = kwargs.pop('debug', None)
        self.slash_mode = kwargs.pop('slash_mode', S_REDIRECT)
        if kwargs:
            raise TypeError('unexpected keyword args: %r' % kwargs.keys())
        self.resources = dict(resources or {})
        resource_conflicts = [r for r in RESERVED_ARGS if r in self.resources]
        if resource_conflicts:
            raise NameError('resource names conflict with builtins: %r' %
                            resource_conflicts)
        self.middlewares = list(middlewares or [])
        check_middlewares(self.middlewares)
        self.render_factory = render_factory

        routes = routes or []
        self.routes = []
        self._null_route = NullRoute()
        self._null_route.bind(self)
        for entry in routes:
            self.add(entry)

    def iter_routes(self):
        for rt in self.routes:
            yield rt

    def add(self, entry, index=None, rebind_render=True, inherit_slashes=True):
        if index is None:
            index = len(self.routes)
        rf = cast_to_route_factory(entry)
        rebind_render = getattr(rf, 'rebind_render', rebind_render)
        kwargs = {'rebind_render': rebind_render,
                  'inherit_slashes': inherit_slashes}
        for route in rf.iter_routes():
            route.bind(self, **kwargs)
            self.routes.insert(index, route)
            index += 1

    def __call__(self, environ, start_response):
        request = self.request_type(environ)
        response = self.dispatch(request)
        return response(environ, start_response)

    def dispatch(self, request):
        url_path = request.path
        method = request.method

        _excs = []
        allowed_methods = set()
        for route in self.routes:
            params = route.match_path(url_path)
            if params is None:
                continue
            method_allowed = route.match_method(method)
            if not method_allowed:
                allowed_methods.update(route.methods)
                _excs.append((route, MethodNotAllowed(allowed_methods)))
                continue
            is_branch = route.pattern.endswith('/')
            normalized_path = normalize_path(url_path, is_branch)
            if normalized_path != url_path:
                if self.slash_mode == S_REDIRECT:
                    dest_url = request.host_url.rstrip('/') + normalized_path
                    return redirect(dest_url)
                elif self.slash_mode == S_STRICT:
                    return NotFound(is_breaking=False)
            params.update(self.resources)
            try:
                ep_res = route.execute(request, **params)
                if not isinstance(ep_res, BaseResponse):
                    msg = 'expected Response, received %r' % type(ep_res)
                    raise InternalServerError(msg)
                return ep_res
            except Exception as e:
                if not isinstance(e, BaseResponse):
                    if self.debug:
                        raise
                    exc_info = ExceptionInfo.from_current()
                    tmp_msg = repr(exc_info)
                    e = InternalServerError(tmp_msg, traceback=exc_info)
                _excs.append((route, e))
                if getattr(e, 'is_breaking', True):
                    break
        if _excs:
            return _excs[-1][-1]
        return self._null_route.execute(request, **self.resources)


class SubApplication(object):
    def __init__(self, prefix, app, rebind_render=False, inherit_slashes=True):
        self.prefix = prefix.rstrip('/')
        self.app = app
        self.rebind_render = rebind_render
        self.inherit_slashes = inherit_slashes

    def iter_routes(self):
        # TODO: if `self.app` is `application` don't re-embed?
        for routes in self.app.iter_routes():
            for rt in routes.iter_routes():
                if isinstance(rt, NullRoute):
                    continue
                yld = rt.empty()
                yld.pattern = self.prefix + rt.pattern
                if self.inherit_slashes:
                    yld.slash_mode = self.app.slash_mode
                yld._compile()
                yield yld


class Application(BaseApplication):
    def serve(self,
              address='0.0.0.0',
              port=5000,
              use_meta=True,
              use_lint=True,
              use_reloader=True,
              use_debugger=True,
              use_static=True,
              static_prefix='static',
              static_path=None, **kw):
        parser = create_dev_server_parser()
        args, _ = parser.parse_known_args()

        address = args.address or address
        port = args.port if args.port is not None else port
        kw['use_reloader'] = args.use_reloader and use_reloader
        kw['use_debugger'] = args.use_debugger and use_debugger
        if kw['use_debugger']:
            self.debug = True
        # kw['processes'] = args.processes or processes
        use_meta = args.use_meta and use_meta
        use_lint = args.use_lint and use_lint
        use_static = args.use_static and use_static

        wrapped_wsgi = self
        if use_meta:
            from meta import MetaApplication
            self.add(('/_meta/', MetaApplication))
        if use_static:
            from static import StaticApplication
            static_path = args.static_path or static_path or \
                os.path.join(os.getcwd(), 'static')
            static_prefix = args.static_prefix or static_prefix
            static_prefix = '/' + unicode(static_prefix).lstrip('/')
            static_app = StaticApplication(static_path)
            self.add((static_prefix, static_app), index=0)
        if use_lint:
            from werkzeug.contrib.lint import LintMiddleware
            wrapped_wsgi = LintMiddleware(wrapped_wsgi)
        if kw.get('_jk_just_testing'):
            return True
        run_simple(address, port, wrapped_wsgi, **kw)


def create_dev_server_parser():
    parser = ArgumentParser()
    parser.add_argument('--address')
    parser.add_argument('--port', type=int)
    parser.add_argument('--static-path')
    parser.add_argument('--static-prefix')
    parser.add_argument('--no-static', dest='use_static',
                        action='store_false')
    parser.add_argument('--no-meta', dest='use_meta',
                        action='store_false')
    parser.add_argument('--no-reloader', dest='use_reloader',
                        action='store_false')
    parser.add_argument('--no-debugger', dest='use_debugger',
                        action='store_false')
    parser.add_argument('--no-wsgi-lint', dest='use_lint',
                        action='store_false')
    parser.add_argument('--processes', type=int, help="number of"
                        " processes, if you want a forking server")
    return parser

"""
Notes
=====

TODO: divide up paths by HTTP method (minor optimization for match speed)
TODO: special handling for HTTPExceptions objects raised in debug mode
TODO: should TracebackInfo optionally know about exc_type and exc_msg?

Note to self: Raising and returning an exception should look basically the
same in production mode.

Potentially conflicting rebindables:

* render (green-path and red)
* slash behavior
* debug flag
"""
