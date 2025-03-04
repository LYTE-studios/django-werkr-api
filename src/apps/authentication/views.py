import datetime
from http import HTTPStatus

from apps.authentication.managers.user_manager import UserManager
from apps.authentication.utils.customer_util import CustomerUtil
from apps.authentication.utils.encryption_util import EncryptionUtil
from apps.authentication.utils.pass_reset_util import CustomPasswordResetUtil
from apps.authentication.utils.worker_util import WorkerUtil
from apps.authentication.utils.profile_util import ProfileUtil
from apps.core.assumptions import CMS_GROUP_NAME, CUSTOMERS_GROUP_NAME
from apps.core.assumptions import (
    WORKERS_GROUP_NAME
)
from apps.core.model_exceptions import DeserializationException
from apps.core.models.settings import Settings
from apps.core.utils.formatters import FormattingUtil
from apps.core.utils.wire_names import *
from apps.jobs.models import Job, JobState
from apps.jobs.services.statistics_service import StatisticsService
from django.contrib.auth.models import Group
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden, HttpRequest, HttpResponse, HttpResponseRedirect
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.exceptions import ValidationError

from apps.authentication.models.dashboard_flow import JobType, Location, SituationType, WorkType, UserJobType

from .models import DashboardFlow
from .utils.authentication_util import AuthenticationUtil
from .utils.jwt_auth_util import JWTAuthUtil
from .serializers import WorkerProfileSerializer, DashboardFlowSerializer
from .models.profiles.worker_profile import WorkerProfile
from django.contrib.auth import get_user_model, login

User = get_user_model()


class BaseClientView(APIView):
    """
    Base view for authentication using only the client secret.
    """

    permission_classes = []

    group = None

    # Override this to allow different groups.
    groups = [
        CUSTOMERS_GROUP_NAME,
        WORKERS_GROUP_NAME,
        CMS_GROUP_NAME,
    ]
    allowed_methods = ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']

    def options(self, request, **kwargs):
        """
        Handles OPTIONS requests to provide allowed methods.

        Args:
            request (HttpRequest): The HTTP request object.
            **kwargs: Additional keyword arguments.

        Returns:
            HttpResponse: An HTTP response with allowed methods.
        """
        response = HttpResponse()
        response['allow'] = ','.join(self.allowed_methods)
        return response

    def dispatch(self, request: HttpRequest, *args, **kwargs):
        """
        Dispatch method to handle the request.

        This method checks the client secret and ensures the user belongs to one of the allowed groups.
        If the checks pass, it calls the parent class's dispatch method.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            HttpResponse: The HTTP response object.
        """
        if request.method == 'OPTIONS':
            return super(BaseClientView, self).dispatch(request, *args, **kwargs)

        self.group = AuthenticationUtil.check_client_secret(request)

        in_group = False

        if not self.group:
            return HttpResponseForbidden()

        if self.group.name in self.groups:
            in_group = True

        if not in_group:
            return HttpResponseForbidden()

        return super(BaseClientView, self).dispatch(request, *args, **kwargs)


class JWTBaseAuthView(APIView):
    """
    Base view for authentication using JWT token auth.

    This view provides a base implementation for views that require JWT token authentication.
    It checks the client secret and the JWT token, and ensures the user belongs to one of the allowed groups.

    Attributes:
        groups (list): List of allowed group names.
        token (AccessToken): The JWT token extracted from the request.
        user (User): The authenticated user.
        group (Group): The group to which the authenticated user belongs.
    """

    permission_classes = []

    # Override this to allow different groups.
    groups = [
        CUSTOMERS_GROUP_NAME,
        WORKERS_GROUP_NAME,
        CMS_GROUP_NAME,
    ]

    token: AccessToken
    user: User
    group: Group

    def dispatch(self, request: HttpRequest, *args, **kwargs):
        """
        Dispatch method to handle the request.

        This method checks the client secret and the JWT token, and ensures the user belongs to one of the allowed groups.
        If the checks pass, it calls the parent class's dispatch method.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            HttpResponse: The HTTP response object.
        """
        if request.user.is_authenticated:
            self.user = request.user
            self.group = request.user.groups.first()

            return super(JWTBaseAuthView, self).dispatch(request, *args, **kwargs)

        self.group = AuthenticationUtil.check_client_secret(request)

        auth_token = JWTAuthUtil.check_for_authentication(request)

        if auth_token is None:
            return HttpResponseForbidden()

        try:
            self.user = User.objects.get(id=auth_token.get('user_id'))
        except User.DoesNotExist:
            return HttpResponseForbidden()

        in_group = False

        for group in Group.objects.filter(user=self.user):
            if group.name in self.groups:
                in_group = True

        if not in_group:
            return HttpResponseForbidden()

        self.token = auth_token

        return super(JWTBaseAuthView, self).dispatch(request, *args, **kwargs)


class JWTAuthenticationView(BaseClientView):
    """
    View for obtaining JWT tokens.
    """

    def post(self, request):
        formatter = FormattingUtil(data=request.data)

        try:
            password = formatter.get_value('password', required=True)
            email = formatter.get_value('email', required=True)
        except DeserializationException as e:
            return Response({'message': e.args}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'message': e.args}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        tokens = JWTAuthUtil.authenticate(email=email, password=password, group=self.group)

        if not tokens or tokens == {}:
            return Response({'message': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        return Response(tokens)


class ValidateRegistrationView(BaseClientView):

    def post(self, request):
        """
        Handles POST requests to validate a registration.

        Args:
            request (HttpRequest): The HTTP request object.

        Returns:
            Response: A JSON response indicating the result of the registration validation.
        """
        formatter = FormattingUtil(data=request.data)

        try:
            email = formatter.get_email(k_email, required=True)
        except Exception as e:
            return Response({'message': e.args}, status=status.HTTP_400_BAD_REQUEST)


        try:
            User.objects.get(email=email)
            
            return Response({'message': 'User already exists'}, status=status.HTTP_409_CONFLICT)
        except User.DoesNotExist:

            return Response()
        except Exception as e:

            return Response({'message': e.args}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            


class JWTRefreshView(TokenRefreshView):
    """
    View for refreshing JWT tokens.
    """
    pass


class JWTTestConnectionView(JWTBaseAuthView):
    """
    View for testing JWT connection.
    """

    def get(self, request):
        """
        Handles GET requests to test the connection.

        Args:
            request (HttpRequest): The HTTP request object.

        Returns:
            Response: A JSON response indicating the connection is successful.
        """
        if not self.user:
            return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)
        
        return Response({
            "id": self.user.id,
            "email": self.user.email,
            "first_name": self.user.first_name,
            "last_name": self.user.last_name,
        })


class ProfileMeView(JWTBaseAuthView):
    """
    View for retrieving and updating the authenticated user's profile.
    """

    def get(self, request):
        """
        Handles GET requests to retrieve the user's profile.

        Args:
            request (HttpRequest): The HTTP request object.

        Returns:
            Response: A JSON response containing the user's profile data.
        """
        profile_picture = ProfileUtil.get_user_profile_picture_url(self.user) 

        data = {
            'user_id': self.user.id,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'email': self.user.email,
            'description': self.user.description,
            'profile_picture': profile_picture,
            'phone_number': self.user.phone_number,
            'language': getattr(Settings.objects.filter(id=self.user.settings_id).first(), 'language',
                                None)
        }

        if hasattr(self.user, 'customer_profile'):
            customer = self.user.customer_profile
            if customer is not None:
                data.update({
                    'tax_number': customer.tax_number,
                    'company_name': customer.company_name,
                    'customer_billing_address': customer.customer_billing_address.to_model_view() if customer.customer_billing_address else None,
                    'address': customer.customer_address.to_model_view() if customer.customer_address else None,
                })
        if hasattr(self.user, 'worker_profile'):
            worker = self.user.worker_profile
            if worker is not None:
                data.update({
                    'iban': worker.iban,
                    'ssn': worker.ssn,
                    'address': worker.worker_address.to_model_view() if worker.worker_address else None,
                    'date_of_birth': FormattingUtil.to_timestamp(worker.date_of_birth),
                    'place_of_birth': worker.place_of_birth,
                    'accepted': worker.accepted,
                    'hours': worker.hours,
                })
        if hasattr(self.user, 'admin_profile'):
            admin = self.user.admin_profile
            if admin is not None:
                data.update({
                    'session_duration': admin.session_duration,
                })

        return Response(data)

    def put(self, request):
        """
        Handles PUT requests to update the user's profile.

        Args:
            request (HttpRequest): The HTTP request object.

        Returns:
            Response: A JSON response containing the updated user ID.
        """
        formatter = FormattingUtil(data=request.data)

        try:
            first_name = formatter.get_value('first_name')
            last_name = formatter.get_value('last_name')
            email = formatter.get_email('email')
            description = formatter.get_value('description')
        except DeserializationException as e:
            return Response({'message': e.args}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'message': e.args}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        self.user.first_name = first_name or self.user.first_name
        self.user.last_name = last_name or self.user.last_name
        self.user.email = email or self.user.email
        self.user.description = description or self.user.description

        if hasattr(self.user, 'customer_profile'):
            try:
                tax_number = formatter.get_value('tax_number')
                company_name = formatter.get_value('company_name')
                customer_address = formatter.get_address('address')
                customer_billing_address = formatter.get_address('billing_address')
            except DeserializationException as e:
                return Response({'message': e.args}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({'message': e.args}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            customer = self.user.customer_profile
            customer.tax_number = tax_number or customer.tax_number
            customer.company_name = company_name or customer.company_name
            customer.customer_address = customer_address or customer.customer_address
            customer.customer_billing_address = customer_billing_address or customer.customer_billing_address
            customer.customer_address.save()
            customer.customer_billing_address.save()
            customer.save()

        if hasattr(self.user, 'worker_profile'):
            try:
                iban = formatter.get_value('iban')
                ssn = formatter.get_value('ssn')
                worker_address = formatter.get_address('address')
                date_of_birth = formatter.get_date('date_of_birth')
                place_of_birth = formatter.get_value('place_of_birth')
                accepted = formatter.get_value('accepted')
                hours = formatter.get_value('hours')
            except DeserializationException as e:
                return Response({'message': e.args}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({'message': e.args}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            worker = self.user.worker_profile
            worker.iban = iban or worker.iban
            worker.ssn = ssn or worker.ssn
            worker.worker_address = worker_address or worker.worker_address
            worker.date_of_birth = date_of_birth or worker.date_of_birth
            worker.place_of_birth = place_of_birth or worker.place_of_birth
            worker.accepted = accepted if accepted is not None else worker.accepted
            worker.hours = hours or worker.hours
            worker.worker_address.save()
            worker.save()

        if hasattr(self.user, 'admin_profile'):
            try:
                session_duration = formatter.get_value('session_duration')
            except DeserializationException as e:
                return Response({'message': e.args}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({'message': e.args}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            admin = self.user.admin_profile
            admin.session_duration = session_duration or admin.session_duration
            admin.save()

        self.user.save()

        return Response({'user_id': self.user.id})


class LanguageSettingsView(JWTBaseAuthView):
    """
    View for managing user language settings.
    """

    def get(self, request):
        """
        Handles GET requests to retrieve available languages.

        Args:
            request (HttpRequest): The HTTP request object.

        Returns:
            JsonResponse: A JSON response containing the list of available languages.
        """
        languages = sorted(set(setting.language for setting in Settings.objects.all() if setting.language))
        return JsonResponse({'languages': languages})

    def put(self, request):
        """
        Handles PUT requests to update the user's language setting.

        Args:
            request (HttpRequest): The HTTP request object.

        Returns:
            Response: A JSON response containing the updated language setting.
        """
        formatter = FormattingUtil(data=request.data)

        try:
            language = formatter.get_value('language', required=True)
        except DeserializationException as e:
            return Response({'message': e.args}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'message': e.args}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if language:
            settings = self.user.settings or Settings.objects.create(language=language)
            settings.language = language
            settings.save()
            self.user.settings = settings
            self.user.save()

        return Response({'language': self.user.settings.language})


class UploadUserProfilePictureView(JWTBaseAuthView):
    """
    View for managing user profile pictures.
    """

    def get(self, request, *args, **kwargs):
        """
        Handles GET requests to retrieve the user's profile picture URL.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: A JSON response containing the profile picture URL.
        """
        profile_user = self.user

        profile_picture_url = profile_user.profile_picture.url if profile_user.profile_picture else None
        
        return Response({'profile_picture': profile_picture_url})

    def put(self, request, *args, **kwargs):
        """
        Handles PUT requests to update the user's profile picture.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: An empty response indicating successful update.
            HttpResponseBadRequest: If the request data is empty.
        """
        profile_user = self.user

        if not request.data:
            return HttpResponseBadRequest()

        profile_user.profile_picture = next(iter(request.data.values()))
        profile_user.save()

        return Response(status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        profile_user = self.user

        if not request.data:
            return HttpResponseBadRequest()

        profile_user.profile_picture = None
        profile_user.save()

        return Response(status=status.HTTP_200_OK)

class PasswordResetRequestView(BaseClientView):
    """
    View for initiating a password reset request.
    """

    def post(self, request, *args, **kwargs):
        """
        Handles POST requests to send a password reset email.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: A JSON response indicating the result of the password reset request.
        """
        formatter = FormattingUtil(data=request.data)

        try:
            email = formatter.get_email(k_email, required=True)
        except Exception as e:
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response({k_message: 'Email not found.'}, status=HTTPStatus.NOT_FOUND)  # Changed to 404

        try:
            pass_reset_util = CustomPasswordResetUtil()
            if not pass_reset_util.send_reset_code(user):
                raise Exception("Failed to send password reset email.")
        except Exception as e:
            return Response({k_message: str(e)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

        return Response({k_message: 'Password reset email has been sent.'}, status=HTTPStatus.OK)

class VerifyCodeView(BaseClientView):
    """
    View for verifying a password reset code.
    """

    def post(self, request, *args, **kwargs):
        """
        Handles POST requests to verify a password reset code.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: A JSON response containing a temporary token if the code is verified.
            Response: A response with an error message and status code if the code is not verified.
        """
        formatter = FormattingUtil(data=request.data)

        try:
            email = formatter.get_value(k_email, required=True)
            code = formatter.get_value(k_code, required=True)
        except Exception as e:
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({k_message: 'Email not found.'}, status=HTTPStatus.BAD_REQUEST)

        pass_reset_util = CustomPasswordResetUtil()
        if pass_reset_util.verify_code(user, code):
            token = pass_reset_util.create_temporary_token_for_user(user, code)
            return Response({k_token: token}, status=HTTPStatus.OK)
        else:
            return Response({k_message: 'Code not verified.'}, status=HTTPStatus.FORBIDDEN)


class ResetPasswordView(BaseClientView):
    """
    Reset password view
    """

    def post(self, request, *args, **kwargs):
        """
        Handles POST requests to reset the user's password.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: A JSON response indicating the result of the password reset.
        """
        formatter = FormattingUtil(data=request.data)

        try:
            # Extract required fields from the request data
            token = formatter.get_value(k_token, required=True)
            code = formatter.get_value(k_code, required=True)
            password = formatter.get_value(k_password, required=True)
        except Exception as e:
            # Return a bad request response if any required field is missing or invalid
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)

        pass_reset_util = CustomPasswordResetUtil()
        user = pass_reset_util.get_user_by_token_and_code(token, code)
        if user:
            # Encrypt the new password and update the user's password
            password, salt = EncryptionUtil.encrypt(password)
            user.password = password
            user.salt = salt
            user.save()

            # Return a success response
            return Response({k_message: 'Password has been reset.'}, status=HTTPStatus.OK)
        else:
            # Return a bad request response if the token or code is invalid or expired
            return Response({k_message: 'Invalid or expired token'}, status=HTTPStatus.BAD_REQUEST)


class DashboardFlowView(BaseClientView):

    def get(self, request):

        job_types = [job_type.to_model_view() for job_type in JobType.objects.all().order_by('weight')] 

        situation_types = [situation_type.to_model_view() for situation_type in SituationType.objects.all().order_by('weight')]

        work_types = [work_type.to_model_view() for work_type in WorkType.objects.all().order_by('weight')]

        locations = [location.to_model_view() for location in Location.objects.all().order_by('weight')]

        return Response({
            'job_types': job_types,
            'situation_types': situation_types,
            'work_types': work_types,
            'locations': locations,
        })

class WorkerRegisterView(BaseClientView):
    """
    [WORKERS]

    POST

    View for registering as a worker.
    """

    groups = [
        WORKERS_GROUP_NAME,
    ]

    def post(self, request: HttpRequest):
        """
        Handles POST requests to register a new worker.

        Args:
            request (HttpRequest): The HTTP request object.

        Returns:
            Response: A JSON response containing the ID of the created user if valid.
        """
        formatter = FormattingUtil(data=request.data)

        # Required fields
        try:
            email = formatter.get_email(k_email, required=True)
            password = formatter.get_value(k_password, required=True)

            work_type_ids = formatter.get_value('work_types', required=False)
            situation_type_ids = formatter.get_value('situation_types', required=False)
            job_type_ids = formatter.get_value('job_types', required=False)
            location_ids = formatter.get_value('locations', required=False)

            if work_type_ids:
                work_types = WorkType.objects.filter(id__in=[work_type.get('id', None) for work_type in work_type_ids])
            else:
                work_types = []
            if situation_type_ids:
                situation_types = SituationType.objects.filter(id__in=[situation_type.get('id', None) for situation_type in situation_type_ids])
            else:
                situation_types = []
            if job_type_ids:
                job_types = []
                for job_type in job_type_ids:
                    job_types.append(UserJobType.objects.create(name_id=job_type.get('id', None), experience_type=job_type.get('mastery', None)))
            else:
                job_types = []
            if location_ids:
                locations = Location.objects.filter(id__in=[location.get('id', None) for location in location_ids])
            else:    
                locations = []

            first_name = formatter.get_value(k_first_name, required=False)
            last_name = formatter.get_value(k_last_name, required=False)
            date_of_birth = formatter.get_date(k_date_of_birth, required=False)
            iban = formatter.get_value(k_tax_number, required=False)
            place_of_birth = formatter.get_value(k_place_of_birth, required=False)
            ssn = formatter.get_value(k_company, required=False)
            worker_address = formatter.get_address(k_address, required=False)
        except DeserializationException as e:
            # If the inner validation fails, this throws an error
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            # Unhandled exception
            return Response({k_message: e.args}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

        if User.objects.filter(email=email).exists():
            return Response({k_message: 'User already exists'}, status=HTTPStatus.METHOD_NOT_ALLOWED)

        # Encrypt the password
        password, salt = EncryptionUtil.encrypt(password)

        # Create the user with the encrypted password
        user = User(
            username=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            salt=salt,
            email=email,
        )

        # Use the manager to create the user
        user = UserManager.create_user(user)

        # Create the worker profile
        UserManager.create_worker_profile(
            user=user,
            iban=iban,
            ssn=ssn,
            worker_address=worker_address,
            date_of_birth=date_of_birth,
            place_of_birth=place_of_birth,
        )

        dashboard_flow = DashboardFlow.objects.create(
            user=user,
        )

        dashboard_flow.situation_types.add(*situation_types)
        dashboard_flow.work_types.add(*work_types)
        dashboard_flow.locations.add(*locations)

        dashboard_flow.job_types.add(*job_types)

        dashboard_flow.save()

        # Get the workers group
        group = Group.objects.get(name=WORKERS_GROUP_NAME)

        # Add user to group
        group.user_set.add(user)

        # Save the group
        group.save()

        # Returns the user's id
        return Response({k_id: user.id})


class StatisticsView(JWTBaseAuthView):
    """
    [WORKERS]

    POST

    View for retrieving worker statistics based on a specified time frame (week or month).
    """

    groups = [
        WORKERS_GROUP_NAME,
    ]

    def post(self, request: HttpRequest):
        """
        Handles POST requests to retrieve worker statistics.

        Args:
            request (HttpRequest): The HTTP request object.

        Returns:
            JsonResponse: A JSON response containing the worker statistics.
            Response: A response with an error message and status code if there is an error in the request data.
        """
        formatter = FormattingUtil(data=request.data)

        try:
            worker_id = formatter.get_value(k_worker_id, required=True)
            time_frame = formatter.get_value(k_time_frame, required=True)
        except DeserializationException as e:
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            return Response({k_message: e.args}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

        if time_frame not in [k_week, k_month]:
            return Response({k_message: 'Invalid time frame'}, status=HTTPStatus.BAD_REQUEST)

        return self.statistics_view(request, time_frame, worker_id)

    def statistics_view(self, request, time_frame, worker_id):
        """
        Retrieves worker statistics based on the specified time frame.

        Args:
            request (HttpRequest): The HTTP request object.
            time_frame (str): The time frame for the statistics ('week' or 'month').
            worker_id (int): The ID of the worker.

        Returns:
            JsonResponse: A JSON response containing the worker statistics.
        """
        today = datetime.date.today()

        if time_frame == k_week:
            stats = []
            for i in range(3):
                week_start = today - datetime.timedelta(days=(today.weekday() + 7 * i))
                week_end = week_start + datetime.timedelta(days=6)
                week_stats = StatisticsService.get_weekly_stats(worker_id, week_start, week_end)
                stats.append(week_stats)

        elif time_frame == k_month:
            stats = []
            for i in range(3):
                year_stats = StatisticsService.get_monthly_stats(worker_id, today.year - i)
                stats.append(year_stats)

        return JsonResponse({k_statistics: stats})


class WorkerDetailView(JWTBaseAuthView):
    """
    [ALL]

    GET

    A view for getting worker details.
    """

    # Overrides the app types with access to this view
    app_types = [
        CMS_GROUP_NAME,
    ]

    def get(self, request: HttpRequest, *args, **kwargs):
        """
        Handles GET requests to retrieve worker details.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: A JSON response containing the worker details.
            HttpResponseNotFound: If the worker does not exist.
        """
        try:
            worker = User.objects.get(id=kwargs['id'], groups__name__contains=WORKERS_GROUP_NAME)
        except User.DoesNotExist:
            return HttpResponseNotFound()

        return Response(data=WorkerUtil.to_worker_view(worker))

    def delete(self, request: HttpRequest, *args, **kwargs):
        """
        Handles DELETE requests to remove a worker.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: An empty response indicating successful deletion.
            HttpResponseNotFound: If the worker does not exist.
        """
        try:
            worker = User.objects.get(id=kwargs['id'], groups__name__contains=WORKERS_GROUP_NAME)
        except User.DoesNotExist:
            return HttpResponseNotFound()

        my_group = Group.objects.get(name=WORKERS_GROUP_NAME)
        my_group.user_set.remove(worker)
        my_group.save()

        return Response()

    def put(self, request: HttpRequest, *args, **kwargs):
        """
        Handles PUT requests to update worker details.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: An empty response indicating successful update.
            Response: A response with an error message and status code if there is an error in the request data.
        """
        try:
            worker = User.objects.get(id=kwargs['id'], groups__name__contains=WORKERS_GROUP_NAME)
        except User.DoesNotExist:
            return HttpResponseNotFound()

        formatter = FormattingUtil(data=request.data)

        try:
            first_name = formatter.get_value(k_first_name)
            last_name = formatter.get_value(k_last_name)
            email = formatter.get_email(k_email)
            address = formatter.get_address(k_address)
            date_of_birth = formatter.get_date(k_date_of_birth)
            billing_address = formatter.get_address(k_billing_address)
            phone_number = formatter.get_value(k_phone_number)
            iban = formatter.get_value(k_iban)
            ssn = formatter.get_value(k_ssn)
            worker_type = formatter.get_value(k_worker_type)
        except DeserializationException as e:
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            return Response({k_message: e.args}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

        worker.first_name = first_name or worker.first_name
        worker.last_name = last_name or worker.last_name
        worker.email = email or worker.email
        worker.phone_number = phone_number or worker.phone_number

        worker.worker_profile.worker_address = address or worker.worker_profile.worker_address
        worker.worker_profile.iban = iban or worker.worker_profile.iban
        worker.worker_profile.ssn = ssn or worker.worker_profile.ssn
        worker.worker_profile.date_of_birth = date_of_birth or worker.worker_profile.date_of_birth
        worker.worker_profile.worker_type = worker_type or worker.worker_profile.worker_type

        if address:
            address.save()
        if billing_address:
            billing_address.save()

        worker.save()
        worker.worker_profile.save()

        return Response()


class WorkersListView(JWTBaseAuthView):
    """
    [CMS]

    GET

    View for CMS users to get workers details.
    """

    # Overrides the app types with access to this view
    app_types = [
        CMS_GROUP_NAME,
    ]

    def get(self, request: HttpRequest, *args, **kwargs):
        """
        Handles GET requests to retrieve a list of workers with optional pagination, sorting, and searching.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: A JSON response containing the list of workers, items per page, and total count.
        """
        item_count = kwargs.get('count', 25)
        page = kwargs.get('page', 1)
        search_term = kwargs.get('search_term')
        sort_term = kwargs.get('sort_term')
        algorithm = kwargs.get('algorithm')
        state = kwargs.get('state')

        block_unaccepted_workers = state != 'registered'

        workers = User.objects.filter(
            groups__name__contains=WORKERS_GROUP_NAME,
            archived=False
        ).filter(worker_profile__accepted=block_unaccepted_workers)

        if sort_term:
            if algorithm == 'descending':
                sort_term = f'-{sort_term}'
            workers = workers.order_by(sort_term)

        if search_term:
            queries = [
                workers.filter(first_name__icontains=search_term)[:10],
                workers.filter(last_name__icontains=search_term)[:10],
                workers.filter(email__icontains=search_term)[:10]
            ]
            data = list({worker for query in queries for worker in query})
        else:
            data = list(workers)

        paginator = Paginator(data, per_page=item_count)
        paginated_workers = paginator.page(page).object_list

        response_data = [
            WorkerUtil.to_worker_view(worker)
            for worker in paginated_workers
        ]

        return Response({
            k_workers: response_data,
            k_items_per_page: paginator.per_page,
            k_total: paginator.count
        })


class AcceptWorkerView(JWTBaseAuthView):
    """
    [ALL]

    POST

    A view for accepting a worker.
    """

    # Overrides the app types with access to this view
    app_types = [
        CMS_GROUP_NAME,
    ]

    def post(self, request: HttpRequest, *args, **kwargs):
        """
        Handles POST requests to accept a worker.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: An empty response indicating successful acceptance.
            HttpResponseNotFound: If the worker does not exist.
        """
        try:
            # Retrieve the worker by id and group
            worker = User.objects.get(id=kwargs['id'], groups__name__contains=WORKERS_GROUP_NAME)
        except User.DoesNotExist:
            return HttpResponseNotFound()

        # Mark the worker as accepted
        worker.accepted = True

        # Save the worker
        worker.save()

        return Response()


class CreateCustomerView(JWTBaseAuthView):
    """
    [CMS]

    POST

    View for creating a new customer.

    Returns id upon success.
    """

    # Overrides the app types with access to this view
    app_types = [
        CMS_GROUP_NAME,
    ]

    def post(self, request: HttpRequest):
        """
        Handles POST requests to create a new customer.

        Args:
            request (HttpRequest): The HTTP request object.

        Returns:
            Response: A JSON response containing the customer id upon success.
            Response: A response with an error message and status code if there is an error in the request data.
        """
        formatter = FormattingUtil(data=request.data)

        try:
            # Required fields
            first_name = formatter.get_value(k_first_name, required=True)
            last_name = formatter.get_value(k_last_name, required=True)
            email = formatter.get_email(k_email, required=True)

            # Optional fields
            address = formatter.get_address(k_address)
            billing_address = formatter.get_address(k_billing_address)
            tax_number = formatter.get_value(k_tax_number)
            company = formatter.get_value(k_company)
        except DeserializationException as e:
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            return Response({k_message: e.args}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

        # Save addresses if provided
        if address:
            address.save()
        if billing_address:
            billing_address.save()

        # Create or get the user
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': email,
                'first_name': first_name,
                'last_name': last_name,
            }
        )

        if not created:
            # Add user to the customer group if not already a member
            if not user.groups.filter(name=CUSTOMERS_GROUP_NAME).exists():
                my_group = Group.objects.get(name=CUSTOMERS_GROUP_NAME)
                my_group.user_set.add(user)

            # Update user details
            user.archived = False
            user.first_name = first_name or user.first_name
            user.last_name = last_name or user.last_name
            user.save()

        # Create customer profile
        UserManager.create_customer_profile(
            user=user,
            tax_number=tax_number,
            company_name=company,
            customer_address=address,
            customer_billing_address=billing_address
        )

        if created:
            # Add user to the customer group
            my_group = Group.objects.get(name=CUSTOMERS_GROUP_NAME)
            my_group.user_set.add(user)
            my_group.save()

        return Response({k_customer_id: user.id})


class CustomersListView(JWTBaseAuthView):
    """
    [CMS]

    GET

    View for CMS users to get customer details.
    """

    # Overrides the app types with access to this view
    app_types = [
        CMS_GROUP_NAME,
    ]

    def get(self, request: HttpRequest, *args, **kwargs):
        """
        Handles GET requests to retrieve a list of customers with optional pagination, sorting, and searching.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: A JSON response containing the list of customers, items per page, and total count.
        """
        # Get pagination parameters from kwargs, with default values
        item_count = kwargs.get('count', 25)
        page = kwargs.get('page', 1)
        search_term = kwargs.get('search_term')
        sort_term = kwargs.get('sort_term')
        algorithm = kwargs.get('algorithm')

        # Get customers with active jobs
        active_job_customers = Job.objects.filter(
            start_time__lt=datetime.datetime.utcnow(),
            job_state=JobState.pending
        ).values_list('customer', flat=True)

        # Filter customers by group and archived status
        customers = User.objects.filter(
            groups__name__contains=CUSTOMERS_GROUP_NAME,
            archived=False
        )

        # Apply sorting if sort_term is provided
        if sort_term:
            if algorithm == 'descending':
                sort_term = f'-{sort_term}'
            customers = customers.order_by(sort_term)

        # Apply search if search_term is provided
        if search_term:
            queries = [
                customers.filter(first_name__icontains=search_term)[:10],
                customers.filter(last_name__icontains=search_term)[:10],
                customers.filter(email__icontains=search_term)[:10]
            ]
            data = list({customer for query in queries for customer in query})
        else:
            data = list(customers)

        # Paginate the customer list
        paginator = Paginator(data, per_page=item_count)
        paginated_customers = paginator.page(page).object_list

        # Convert customers to view format and check for active jobs
        response_data = [
            CustomerUtil.to_customer_view(customer, has_active_job=customer.id in active_job_customers)
            for customer in paginated_customers
        ]

        # Return the paginated customer data
        return Response({
            k_customers: response_data,
            k_items_per_page: paginator.per_page,
            k_total: paginator.count
        })


class CustomerDetailView(JWTBaseAuthView):
    """
    [ALL]

    GET

    A view for getting customer details.
    """

    # Overrides the app types with access to this view
    app_types = [
        CMS_GROUP_NAME,
    ]

    def get(self, request: HttpRequest, *args, **kwargs):
        """
        Handles GET requests to retrieve customer details.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: A JSON response containing the customer details.
            HttpResponseNotFound: If the customer does not exist.
        """
        try:
            customer = User.objects.get(id=kwargs['id'], groups__name__contains=CUSTOMERS_GROUP_NAME)
        except User.DoesNotExist:
            return HttpResponseNotFound()

        return Response(data=CustomerUtil.to_customer_view(customer))

    def delete(self, request: HttpRequest, *args, **kwargs):
        """
        Handles DELETE requests to remove a customer from the group.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: An empty response indicating successful deletion.
            HttpResponseNotFound: If the customer does not exist.
        """
        try:
            customer = User.objects.get(id=kwargs['id'], groups__name__contains=CUSTOMERS_GROUP_NAME)
        except User.DoesNotExist:
            return HttpResponseNotFound()

        my_group = Group.objects.get(name=CUSTOMERS_GROUP_NAME)
        my_group.user_set.remove(customer)

        my_group.save()

        return Response()

    def put(self, request: HttpRequest, *args, **kwargs):
        """
        Handles PUT requests to update customer details.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: An empty response indicating successful update.
            HttpResponseNotFound: If the customer does not exist.
            Response: A response with an error message and status code if there is an error in the request data.
        """
        try:
            customer = User.objects.get(id=kwargs['id'], groups__name__contains=CUSTOMERS_GROUP_NAME)
        except User.DoesNotExist:
            return HttpResponseNotFound()

        formatter = FormattingUtil(data=request.data)

        try:
            first_name = formatter.get_value('first_name')
            last_name = formatter.get_value('last_name')
            email = formatter.get_email('email')
            address = formatter.get_address('address')
            billing_address = formatter.get_address('billing_address')
            tax_number = formatter.get_value('tax_number')
            company = formatter.get_value('company')
            phone_number = formatter.get_value('phone_number')
            special_committee = formatter.get_value('special_committee')
        except DeserializationException as e:
            return Response({'message': e.args}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            return Response({'message': e.args}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

        customer.first_name = first_name or customer.first_name
        customer.last_name = last_name or customer.last_name
        customer.email = email or customer.email
        customer.phone_number = phone_number or customer.phone_number

        customer_profile = customer.customer_profile
        customer_profile.customer_address = address or customer_profile.customer_address
        customer_profile.customer_billing_address = billing_address or customer_profile.customer_billing_address
        customer_profile.tax_number = tax_number or customer_profile.tax_number
        customer_profile.company_name = company or customer_profile.company_name
        customer_profile.special_committee = special_committee or customer_profile.special_committee

        if address:
            address.save()
        if billing_address:
            billing_address.save()

        customer.save()
        customer_profile.save()

        return Response()


class CustomerSearchTermView(JWTBaseAuthView):
    """
    [CMS]

    GET

    View for CMS users to get customer details based on search terms.
    """

    # Overrides the app types with access to this view
    app_types = [
        CMS_GROUP_NAME,
    ]

    def get(self, request: HttpRequest, *args, **kwargs):
        """
        Handles GET requests to search for customers based on a search term.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: A JSON response containing the list of customers matching the search term.
            HttpResponseNotFound: If the search term is not provided.
        """
        search_term = kwargs.get('search_term')
        if not search_term:
            return HttpResponseNotFound()

        customers = User.objects.filter(groups__name__contains=CUSTOMERS_GROUP_NAME)

        queries = [
            customers.filter(first_name__icontains=search_term)[:5],
            customers.filter(last_name__icontains=search_term)[:5],
            customers.filter(email__icontains=search_term)[:5]
        ]

        data = [CustomerUtil.to_customer_view(customer) for query in queries for customer in query.all()]

        return Response({k_customers: list(data)})

class WorkerProfileDetailView(JWTBaseAuthView):
    """
    API view to fetch and view worker profile data for a specific user.
    """

    def get(self, request, user_id, *args, **kwargs):
        worker_profile = get_object_or_404(WorkerProfile, user__id=user_id)
        dashboard_flow = get_object_or_404(DashboardFlow, user__id=user_id)

        worker_profile_serializer = WorkerProfileSerializer(worker_profile)
        dashboard_flow_serializer = DashboardFlowSerializer(dashboard_flow)

        response_data = {
            'worker_profile': worker_profile_serializer.data,
            'dashboard_flow': dashboard_flow_serializer.data
        }

        return Response(response_data, status=status.HTTP_200_OK)
    
class MediaForwardView(APIView):

    permission_classes = []

    def get(self, request, *args, **kwargs):
        from django.conf import settings

        file_location = kwargs["media_url"]

        if file_location is not None:
            return HttpResponseRedirect(redirect_to=settings.STATIC_URL + file_location)

        return HttpResponseNotFound()


class ProfileCompletionView(APIView):

    """
    API Endpoint to evaluate the worker's profile completion.
    Returns completion percentage and missing fields, 
    or raises a ValidationError with detailed missing fields if incomplete.
    """
    
    def get(self, request, worker_id):
        """
        Evaluate the worker's profile completion.
        
        Args:
            request: The HTTP request object.
            worker_id (int): The unique identifier for the worker profile.

        Returns:
            Response: Contains completion percentage and missing fields if complete,
                      or raises a ValidationError with detailed missing fields if incomplete.
        """

        try:
            # Fetch the worker profile based on worker_id
            worker_profile = WorkerProfile.objects.get(user__id=worker_id)
        except WorkerProfile.DoesNotExist:
            raise ValidationError("Worker profile not found.")
        
        # Calculate profile completion
        completion_data = WorkerUtil.calculate_profile_completion(worker_profile.user)
        completion_percentage = completion_data["completion_percentage"]
        missing_fields = completion_data["missing_fields"]
        
        if completion_percentage < 100:
            missing_fields_str = ', '.join([field.capitalize() for field in missing_fields]) or "No mandatory fields completed."
            raise ValidationError(
                f"Profile is incomplete. Completion percentage: {completion_percentage}%. "
                f"Missing fields: {missing_fields_str}"
            )
        
        # Return the completion percentage and empty list of missing fields if 100% complete
        return Response(
            {
                "completion_percentage": completion_percentage,
                "missing_fields": missing_fields or ["None"]
            },
            status=status.HTTP_200_OK
        )