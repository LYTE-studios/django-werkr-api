from apps.core.model_exceptions import NotFoundException


class UserNotFoundException(NotFoundException):
    """
    Exception used when a user could not be found.
    """

    name = 'User'

    pass


class WorkerNotFoundException(NotFoundException):
    """
    Exception used when a worker could not be found.
    """

    name = 'Worker'

    pass


class CustomerNotFoundException(NotFoundException):
    """
    Exception used when a worker could not be found.
    """

    name = 'Customer'

    pass
