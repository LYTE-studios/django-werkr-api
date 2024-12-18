from http import HTTPStatus

from rest_framework.response import Response

from apps.core.utils.wire_names import k_message


class GawBaseException(Exception):
    """
    Base exception for all exceptions
    """

    def get_response(self):
        return Response({k_message: 'An unknown error occurred...'}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    pass


class DeserializationException(GawBaseException):
    """
    Exception used when there's an error processing a model.

    Should produce a bad request error, as this comes from bad user input.
    """

    def get_response(self):
        return Response({k_message: 'Model could not be deserialized.'}, status=HTTPStatus.BAD_REQUEST)

    pass


class NotFoundException(GawBaseException):
    """
    Exception used when a model could not be found.

    Should produce a not found error.
    """

    name = '_'

    def get_response(self):
        return Response({k_message: '{} could not be found'.format(NotFoundException.name)},
                        status=HTTPStatus.NOT_FOUND)

    pass
