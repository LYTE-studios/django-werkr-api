from apps.core.model_exceptions import NotFoundException


class JobNotFoundException(NotFoundException):
    """
    Exception used when a worker could not be found.
    """

    name = "Job"

    pass
