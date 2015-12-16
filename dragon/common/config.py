
# vim: tabstop=4 shiftwidth=4 softtabstop=4

#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
Routines for configuring Dragon
"""

import logging as sys_logging
import os

from eventlet.green import socket
from oslo.config import cfg

from dragon.common import wsgi

from dragon.openstack.common import log as logging

DEFAULT_PORT = 8000

paste_deploy_group = cfg.OptGroup('paste_deploy')
paste_deploy_opts = [
    cfg.StrOpt('flavor',
               help=_("The flavor to use")),
    cfg.StrOpt('api_paste_config', default="api-paste.ini",
               help=_("The API paste config file to use"))]


service_opts = [
    cfg.IntOpt('periodic_interval',
               default=60,
               help='seconds between running periodic tasks'),
    cfg.StrOpt('dragon_stack_user_role',
               default="dragon_stack_user",
               help='Keystone role for dragon template-defined users'),
    cfg.IntOpt('max_template_size',
               default=524288,
               help='Maximum raw byte size of any template.'),
    cfg.IntOpt('max_nested_stack_depth',
               default=3,
               help='Maximum depth allowed when using nested stacks.')]

db_opts = [
    cfg.StrOpt('sql_connection',
               default='mysql://dragon:dragon@localhost/dragon',
               help='The SQLAlchemy connection string used to connect to the '
               'database'),
    cfg.IntOpt('sql_idle_timeout',
               default=3600,
               help='timeout before idle sql connections are reaped')]

engine_opts = [
    cfg.StrOpt('instance_user',
               default='ec2-user',
               help='The default user for new instances'),
    cfg.StrOpt('instance_driver',
               default='dragon.engine.nova',
               help='Driver to use for controlling instances'),
    cfg.StrOpt('deferred_auth_method',
               choices=['password', 'trusts'],
               default='password',
               help=_('Select deferred auth method, '
                      'stored password or trusts'))]

rpc_opts = [
    cfg.StrOpt('host',
               default=socket.gethostname(),
               help='Name of the engine node. '
                    'This can be an opaque identifier.'
                    'It is not necessarily a hostname, FQDN, or IP address.')]

auth_password_group = cfg.OptGroup('auth_password')
auth_password_opts = [
    cfg.BoolOpt('multi_cloud',
                default=False,
                help=_('Allow orchestration of multiple clouds')),
    cfg.ListOpt('allowed_auth_uris',
                default=[],
                help=_('Allowed keystone endpoints for auth_uri when '
                       'multi_cloud is enabled. At least one endpoint needs '
                       'to be specified.'))]
clients_opts = [
    cfg.StrOpt('endpoint_type',
               default='publicURL',
               help=_(
                   'Type of endpoint in Identity service catalog to use '
                   'for communication with the OpenStack service.')),
    cfg.StrOpt('ca_file',
               help=_('Optional CA cert file to use in SSL connections.')),
    cfg.StrOpt('cert_file',
               help=_('Optional PEM-formatted certificate chain file.')),
    cfg.StrOpt('key_file',
               help=_('Optional PEM-formatted file that contains the '
                      'private key.')),
    cfg.BoolOpt('insecure',
                default=False,
                help=_("If set, then the server's certificate will not "
                       "be verified."))]

cfg.CONF.register_opts(db_opts)


def list_opts():
    yield None, rpc_opts
    yield None, engine_opts
    yield None, service_opts
    yield paste_deploy_group.name, paste_deploy_opts
    yield auth_password_group.name, auth_password_opts
    yield 'clients', clients_opts

    for client in ('nova', 'swift', 'neutron', 'cinder',
                   'ceilometer', 'keystone', 'heat', 'glance', 'trove'):
        client_specific_group = 'clients_' + client
        yield client_specific_group, clients_opts

cfg.CONF.register_group(paste_deploy_group)
cfg.CONF.register_group(auth_password_group)

for group, opts in list_opts():
    cfg.CONF.register_opts(opts, group=group)


def _get_deployment_flavor():
    """
    Retrieve the paste_deploy.flavor config item, formatted appropriately
    for appending to the application name.
    """
    flavor = cfg.CONF.paste_deploy.flavor
    return '' if not flavor else ('-' + flavor)


def _get_deployment_config_file():
    """
    Retrieve the deployment_config_file config item, formatted as an
    absolute pathname.
    """
    config_path = cfg.CONF.find_file(
        cfg.CONF.paste_deploy['api_paste_config'])
    if config_path is None:
        return None

    return os.path.abspath(config_path)


def load_paste_app(app_name=None):
    """
    Builds and returns a WSGI app from a paste config file.

    We assume the last config file specified in the supplied ConfigOpts
    object is the paste config file.

    :param app_name: name of the application to load

    :raises RuntimeError when config file cannot be located or application
            cannot be loaded from config file
    """
    if app_name is None:
        app_name = cfg.CONF.prog

    # append the deployment flavor to the application name,
    # in order to identify the appropriate paste pipeline
    app_name += _get_deployment_flavor()

    conf_file = _get_deployment_config_file()
    if conf_file is None:
        raise RuntimeError("Unable to locate config file")

    try:
        app = wsgi.paste_deploy_app(conf_file, app_name, cfg.CONF)

        # Log the options used when starting if we're in debug mode...
        if cfg.CONF.debug:
            cfg.CONF.log_opt_values(logging.getLogger(app_name),
                                    sys_logging.DEBUG)

        return app
    except (LookupError, ImportError) as e:
        raise RuntimeError("Unable to load %(app_name)s from "
                           "configuration file %(conf_file)s."
                           "\nGot: %(e)r" % {'app_name': app_name,
                                             'conf_file': conf_file,
                                             'e': e})
