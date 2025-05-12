from celery import shared_task

@shared_task
def execute_task(func_path, *args, **kwargs):
    """
    Execute a function as a Celery task.
    
    Args:
        func_path (str): Import path to the function (e.g., 'apps.core.utils.my_function')
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function
    """
    from django.utils.module_loading import import_string
    
    try:
        func = import_string(func_path)
        return func(*args, **kwargs)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error executing task {func_path}: {str(e)}")
        raise