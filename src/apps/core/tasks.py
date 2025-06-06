from celery import shared_task, current_task
import logging
from django.utils.module_loading import import_string
import traceback

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def execute_task(self, func_path, *args, **kwargs):
    """
    Execute a function as a Celery task.
    
    Args:
        func_path (str): Import path to the function (e.g., 'apps.core.utils.my_function')
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function
    """
    try:
        # Log task details
        logger.info(f"[DEBUG] Starting task execution:")
        logger.info(f"[DEBUG] Task ID: {self.request.id}")
        logger.info(f"[DEBUG] Root ID: {self.request.root_id}")
        logger.info(f"[DEBUG] Parent ID: {self.request.parent_id}")
        logger.info(f"[DEBUG] Function: {func_path}")
        logger.info(f"[DEBUG] Args: {args}")
        logger.info(f"[DEBUG] Kwargs: {kwargs}")
        logger.info(f"[DEBUG] Stack trace:")
        logger.info(''.join(traceback.format_stack()))

        # Import and execute function
        func = import_string(func_path)
        
        # Log before function execution
        logger.info(f"[DEBUG] About to execute function {func_path}")
        
        result = func(*args, **kwargs)
        
        # Log after function execution
        logger.info(f"[DEBUG] Function {func_path} executed successfully")
        logger.info(f"[DEBUG] Result: {result}")
        
        return result
    except Exception as e:
        logger.error(f"[DEBUG] Error executing task {func_path}: {str(e)}")
        logger.error(f"[DEBUG] Exception traceback: {''.join(traceback.format_tb(e.__traceback__))}")
        raise e