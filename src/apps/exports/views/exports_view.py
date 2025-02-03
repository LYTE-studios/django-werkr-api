


from http import HTTPStatus

from django.http import HttpRequest
from rest_framework.response import Response
from django.core.paginator import Paginator


from core.assumptions import *
from core.features.authentication.views.jwt_base_auth_view import JWTBaseAuthView
from core.features.base.exceptions.core.model_exceptions import DeserializationException
from core.features.base.util.formatting_util import FormattingUtil
from core.features.base.util.wire_names import *
from core.features.exports.managers.export_manager import ExportManager
from core.features.exports.models.export_file import ExportFile
from core.features.profile.utils.profile_util import ProfileUtil


class ExportsView(JWTBaseAuthView):
    """
    [CMS]

    GET | POST

    View for refreshing and getting exports
    """

    groups = [
        CMS_GROUP_NAME,
    ]

    def get(self, request: HttpRequest, *args, **kwargs):
        """
        View for getting a list of all existing exports
        """

        item_count = 25
        page = 1
        sort_term = None
        algorithm = None

        try:
            item_count = kwargs['count']
            page = kwargs['page']
        except KeyError:
            pass
        try:
            sort_term = kwargs['sort_term']
            algorithm = kwargs['algorithm']
        except KeyError:
            pass

        if sort_term is not None:
            if algorithm == 'descending':
                sort_term = '-{}'.format(sort_term)

            export_files = ExportFile.objects.all().order_by(sort_term)

        else:
            export_files = ExportFile.objects.all().order_by('-created')

        paginator = Paginator(export_files, per_page=item_count)

        data = []

        for export in paginator.page(page).object_list:
            data.append(export.to_model_view())

        return Response(data={
            k_exports: data,
            k_items_per_page: paginator.per_page, k_total: len(
            export_files,),
        })


    def post(self, request: HttpRequest):
        """
        Creates the latest monthly export
        """

        formatter = FormattingUtil(data=request.data)

        try:
            start = formatter.get_date(k_start_time)
            end = formatter.get_date(k_end_time)

        except DeserializationException as e:
            # If the inner validation fails, this throws an error
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            # Unhandled exception
            return Response({k_message: e.args}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

        if start is None or end is None:
            start, end =  ExportManager.get_last_month_period()

        ExportManager.create_time_registations_export(start, end)

        ExportManager.create_active_washers_export(start, end)

        return Response()
