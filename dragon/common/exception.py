# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
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

"""Dragon exception subclasses"""

import functools
import urlparse
import sys

from dragon.openstack.common import log as logging


_FATAL_EXCEPTION_FORMAT_ERRORS = False


logger = logging.getLogger(__name__)


class RedirectException(Exception):
    def __init__(self, url):
        self.url = urlparse.urlparse(url)


class KeystoneError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message

    def __str__(self):
        return "Code: %s, message: %s" % (self.code, self.message)


def wrap_exception(notifier=None, publisher_id=None, event_type=None,
                   level=None):
    """This decorator wraps a method to catch any exceptions that may
    get thrown. It logs the exception as well as optionally sending
    it to the notification system.
    """
    # TODO(sandy): Find a way to import nova.notifier.api so we don't have
    # to pass it in as a parameter. Otherwise we get a cyclic import of
    # nova.notifier.api -> nova.utils -> nova.exception :(
    # TODO(johannes): Also, it would be nice to use
    # utils.save_and_reraise_exception() without an import loop
    def inner(f):
        def wrapped(*args, **kw):
            try:
                return f(*args, **kw)
            except Exception as e:
                # Save exception since it can be clobbered during processing
                # below before we can re-raise
                exc_info = sys.exc_info()

                if notifier:
                    payload = dict(args=args, exception=e)
                    payload.update(kw)

                    # Use a temp vars so we don't shadow
                    # our outer definitions.
                    temp_level = level
                    if not temp_level:
                        temp_level = notifier.ERROR

                    temp_type = event_type
                    if not temp_type:
                        # If f has multiple decorators, they must use
                        # functools.wraps to ensure the name is
                        # propagated.
                        temp_type = f.__name__

                    notifier.notify(publisher_id, temp_type, temp_level,
                                    payload)

                # re-raise original exception since it may have been clobbered
                raise exc_info[0], exc_info[1], exc_info[2]

        return functools.wraps(f)(wrapped)
    return inner


class DragonException(Exception):
    """Base Dragon Exception

    To correctly use this class, inherit from it and define
    a 'msg_fmt' property. That msg_fmt will get printf'd
    with the keyword arguments provided to the constructor.

    """
    message = _("An unknown exception occurred.")

    def __init__(self, **kwargs):
        self.kwargs = kwargs

        try:
            self.message = self.message % kwargs
        except KeyError:
            exc_info = sys.exc_info()
            # kwargs doesn't match a variable in the message
            # log the issue and the kwargs
            logger.exception(_('Exception in string format operation'))
            for name, value in kwargs.iteritems():
                logger.error("%s: %s" % (name, value))

            if _FATAL_EXCEPTION_FORMAT_ERRORS:
                raise exc_info[0], exc_info[1], exc_info[2]

    def __str__(self):
        return str(self.message)

    def __unicode__(self):
        return unicode(self.message)


class MissingCredentialError(DragonException):
    message = _("Missing required credential: %(required)s")


class BadAuthStrategy(DragonException):
    message = _("Incorrect auth strategy, expected \"%(expected)s\" but "
                "received \"%(received)s\"")


class AuthBadRequest(DragonException):
    message = _("Connect error/bad request to Auth service at URL %(url)s.")


class AuthUrlNotFound(DragonException):
    message = _("Auth service at URL %(url)s not found.")


class AuthorizationFailure(DragonException):
    message = _("Authorization failed.")


class NotAuthenticated(DragonException):
    message = _("You are not authenticated.")


class Forbidden(DragonException):
    message = _("You are not authorized to complete this action.")


# NOTE(bcwaldon): here for backwards-compatability, need to deprecate.
class NotAuthorized(Forbidden):
    message = _("You are not authorized to complete this action.")


class Invalid(DragonException):
    message = _("Data supplied was not valid: %(reason)s")


class AuthorizationRedirect(DragonException):
    message = _("Redirecting to %(uri)s for authorization.")


class ClientConfigurationError(DragonException):
    message = _("There was an error configuring the client.")


class RequestUriTooLong(DragonException):
    message = _("The URI was too long.")


class ServerError(DragonException):
    message = _("The request returned 500 Internal Server Error"
                "\n\nThe response body:\n%(body)s")


class MaxRedirectsExceeded(DragonException):
    message = _("Maximum redirects (%(redirects)s) was exceeded.")


class InvalidRedirect(DragonException):
    message = _("Received invalid HTTP redirect.")


class NoServiceEndpoint(DragonException):
    message = _("Response from Keystone does not contain a Heat endpoint.")


class RegionAmbiguity(DragonException):
    message = _("Multiple 'image' service matches for region %(region)s. This "
                "generally means that a region is required and you have not "
                "supplied one.")


class UserParameterMissing(DragonException):
    message = _("The Parameter (%(key)s) was not provided.")


class UnknownUserParameter(DragonException):
    message = _("The Parameter (%(key)s) was not defined in template.")


class UserKeyPairMissing(DragonException):
    message = _("The Key (%(key_name)s) could not be found.")


class FlavorMissing(DragonException):
    message = _("The Flavor ID (%(flavor_id)s) could not be found.")


class ImageNotFound(DragonException):
    message = _("The Image (%(image_name)s) could not be found.")


class NoUniqueImageFound(DragonException):
    message = _("Multiple images were found with name (%(image_name)s).")


class InvalidTenant(DragonException):
    message = _("Searching Tenant %(target)s "
                "from Tenant %(actual)s forbidden.")


class ActionError(DragonException):
    message = _("Action (%(action)s) could not be found or could "
                "not be loaded.")


class OrchestrationError(DragonException):
    message = _("Heat stack creation failed (%(reason)s) ")


class SwiftConnectionFailed(DragonException):
    message = _("Connection to swift failed: %(reason)s")


class ResourceFailure(DragonException):
    message = _("%(exc_type)s: %(message)s")

    def __init__(self, exception, resource, action=None):
        if isinstance(exception, ResourceFailure):
            exception = getattr(exception, 'exc', exception)
        self.exc = exception
        self.resource = resource
        self.action = action
        exc_type = type(exception).__name__
        super(ResourceFailure, self).__init__(exc_type=exc_type,
                                              message=str(exception))


class NotSupported(DragonException):
    message = _("%(feature)s is not supported.")


class HTTPExceptionDisguise(Exception):
    """Disguises HTTP exceptions so they can be handled by the webob fault
    application in the wsgi pipeline.
    """

    def __init__(self, exception):
        self.exc = exception
        self.tb = sys.exc_info()[2]


class Error(Exception):
    def __init__(self, message=None):
        super(Error, self).__init__(message)


class NotFound(Error):
    pass


class InvalidContentType(DragonException):
    message = "Invalid content type %(content_type)s"


class RequestLimitExceeded(DragonException):
    message = _('Request limit exceeded: %(message)s')
