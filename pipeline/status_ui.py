#!/usr/bin/env python
#
# Copyright 2010 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Status UI for Google App Engine Pipeline API."""

import logging
import os
import pkgutil
import traceback
import zipfile
from functools import wraps

from django.http import HttpResponse, HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from google.appengine.api import users

try:
  import json
except ImportError:
  import simplejson as json

# Relative imports
import util


_RESOURCE_MAP = {
  '/status': ('ui/status.html', 'text/html'),
  '/status.css': ('ui/status.css', 'text/css'),
  '/status.js': ('ui/status.js', 'text/javascript'),
  '/list': ('ui/root_list.html', 'text/html'),
  '/list.css': ('ui/root_list.css', 'text/css'),
  '/list.js': ('ui/root_list.js', 'text/javascript'),
  '/common.js': ('ui/common.js', 'text/javascript'),
  '/common.css': ('ui/common.css', 'text/css'),
  '/jquery-1.4.2.min.js': ('ui/jquery-1.4.2.min.js', 'text/javascript'),
  '/jquery.treeview.min.js': ('ui/jquery.treeview.min.js', 'text/javascript'),
  '/jquery.cookie.js': ('ui/jquery.cookie.js', 'text/javascript'),
  '/jquery.timeago.js': ('ui/jquery.timeago.js', 'text/javascript'),
  '/jquery.ba-hashchange.min.js': (
      'ui/jquery.ba-hashchange.min.js', 'text/javascript'),
  '/jquery.json.min.js': ('ui/jquery.json.min.js', 'text/javascript'),
  '/jquery.treeview.css': ('ui/jquery.treeview.css', 'text/css'),
  '/treeview-default.gif': ('ui/images/treeview-default.gif', 'image/gif'),
  '/treeview-default-line.gif': (
      'ui/images/treeview-default-line.gif', 'image/gif'),
  '/treeview-black.gif': ('ui/images/treeview-black.gif', 'image/gif'),
  '/treeview-black-line.gif': (
      'ui/images/treeview-black-line.gif', 'image/gif'),
  '/images/treeview-default.gif': (
      'ui/images/treeview-default.gif', 'image/gif'),
  '/images/treeview-default-line.gif': (
      'ui/images/treeview-default-line.gif', 'image/gif'),
  '/images/treeview-black.gif': (
      'ui/images/treeview-black.gif', 'image/gif'),
  '/images/treeview-black-line.gif': (
      'ui/images/treeview-black-line.gif', 'image/gif'),
}

@csrf_exempt
def statusui_handler(request, resource=''):
  """Render the status UI."""
  import pipeline  # Break circular dependency
  if pipeline._ENFORCE_AUTH:
    if users.get_current_user() is None:
      logging.debug('User is not logged in')
      return redirect(users.create_login_url(request.build_absolute_uri()))

    if not users.is_current_user_admin():
      logging.debug('User is not admin: %r', users.get_current_user())
      return HttpResponseForbidden()

  if resource not in _RESOURCE_MAP:
    logging.debug('Could not find: %s', resource)
    return HttpResponseNotFound()

  relative_path, content_type = _RESOURCE_MAP[resource]
  path = os.path.join(os.path.dirname(__file__), relative_path)

  # It's possible we're inside a zipfile (zipimport).  If so,
  # __file__ will start with 'something.zip'.
  if ('.zip' + os.sep) in path:
    (zip_file, zip_path) = os.path.relpath(path).split('.zip' + os.sep, 1)
    content = zipfile.ZipFile(zip_file + '.zip').read(zip_path)
  else:
    try:
      content = pkgutil.get_data(__name__, relative_path)
    except AttributeError:  # Python < 2.6.
      content = open(path, 'rb').read()

  response = HttpResponse(content=content, content_type=content_type)

  if not pipeline._DEBUG:
    response["Cache-Control"] = "public, max-age=300"

  return response


def _rpc_handler(func):
  """Base handler for JSON-RPC responses.

  Functions that use this decorator should just return a dict of JSON-serializable data
  """
  @wraps(func)
  def wrapper(request):
    import pipeline  # Break circular dependency
    if pipeline._ENFORCE_AUTH:
      if not users.is_current_user_admin():
        logging.debug('User is not admin: %r', users.get_current_user())
        return HttpResponseForbidden(content='Forbidden')

    # XSRF protection
    if (not pipeline._DEBUG and
        not request.is_ajax()):
      logging.debug('Request missing X-Requested-With header')
      return HttpResponseForbidden(content='Request missing X-Requested-With header')

    try:
      json_response = func(request)
      output = json.dumps(json_response, cls=util.JsonEncoder)
    except Exception, e:
      json_response = dict(
        error_class=e.__class__.__name__,
        error_message=str(e),
        error_traceback=traceback.format_exc(),
      )
      output = json.dumps(json_response, cls=util.JsonEncoder)

    response = HttpResponse(
      content=output,
      content_type='application/json'
    )
    response['Cache-Control'] = 'no-cache'
    return response

  return wrapper

@csrf_exempt
@_rpc_handler
def treestatus_handler(request):
  """RPC handler for getting the status of all children of root pipeline."""
  import pipeline  # Break circular dependency
  return pipeline.get_status_tree(request.GET.get('root_pipeline_id'))

@csrf_exempt
@_rpc_handler
def classpathlist_handler(request):
  """RPC handler for getting the list of all Pipeline classes defined."""
  import pipeline  # Break circular dependency
  return dict(classPaths=pipeline.get_pipeline_names())

@csrf_exempt
@_rpc_handler
def rootlist_hanlder(request):
  """RPC handler for getting the status of all root pipelines."""
  import pipeline  # Break circular dependency
  return pipeline.get_root_list(
    class_path=request.GET.get('class_path'),
    cursor=request.GET.get('cursor'))
