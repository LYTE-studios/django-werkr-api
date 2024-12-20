import datetime
from http import HTTPStatus

from apps.authentication.managers.user_manager import UserManager
from apps.authentication.models import User
from apps.authentication.utils.customer_util import CustomerUtil
from apps.authentication.utils.encryption_util import EncryptionUtil
from apps.authentication.utils.pass_reset_util import CustomPasswordResetUtil
from apps.authentication.utils.worker_util import WorkerUtil
from apps.core.assumptions import CMS_GROUP_NAME, CUSTOMERS_GROUP_NAME
from apps.core.assumptions import (
    WORKERS_GROUP_NAME
)
from apps.core.model_exceptions import DeserializationException
from apps.core.models.settings import Settings
from apps.core.utils.formatters import FormattingUtil
from apps.core.utils.profile import ProfileUtil
from apps.core.utils.wire_names import *
from apps.jobs.models import Job, JobState
from apps.jobs.services.statistics_service import StatisticsService
from django.contrib.auth.models import Group
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden, HttpRequest, HttpResponse
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import User
from .utils.authentication_util import AuthenticationUtil
from .utils.jwt_auth_util import JWTAuthUtil


class JWTAuthenticationView(TokenObtainPairView):
    pass


class JWTRefreshView(TokenRefreshView):
    pass


class JWTTestConnectionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"message": "Connection successful"})


class JWTBaseAuthView(APIView):
    """
    Base view for authentication using JWT token auth
    """

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


class ProfileMeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile_picture = ProfileUtil.get_user_profile_picture_url(
            request.user) if ProfileUtil.get_user_profile_picture_url(request.user) else None

        data = {
            'user_id': request.user.id,
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
            'description': request.user.description,
            'profile_picture': profile_picture,
            'language': getattr(Settings.objects.filter(id=request.user.settings_id).first(), 'language', None)
        }

        if hasattr(request.user, 'customer_profile'):
            customer = request.user.customer_profile
            data.update({
                'phone_number': customer.phone_number,
                'tax_number': customer.tax_number,
                'company_name': customer.company_name,
                'customer_billing_address': customer.customer_billing_address.to_model_view() if customer.customer_billing_address else None,
                'customer_address': customer.customer_address.to_model_view() if customer.customer_address else None,
            })
        if hasattr(request.user, 'worker_profile'):
            worker = request.user.worker_profile
            data.update({
                'iban': worker.iban,
                'ssn': worker.ssn,
                'worker_address': worker.worker_address.to_model_view() if worker.worker_address else None,
                'date_of_birth': FormattingUtil.to_timestamp(worker.date_of_birth),
                'place_of_birth': worker.place_of_birth,
                'accepted': worker.accepted,
                'hours': worker.hours,
            })
        if hasattr(request.user, 'admin_profile'):
            admin = request.user.admin_profile
            data.update({
                'session_duration': admin.session_duration,
            })

        return Response(data)

    def put(self, request):
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

        request.user.first_name = first_name or request.user.first_name
        request.user.last_name = last_name or request.user.last_name
        request.user.email = email or request.user.email
        request.user.description = description or request.user.description

        if hasattr(request.user, 'customer_profile'):
            try:
                phone_number = formatter.get_value('phone_number')
                tax_number = formatter.get_value('tax_number')
                company_name = formatter.get_value('company_name')
                customer_address = formatter.get_address('address')
                customer_billing_address = formatter.get_address('billing_address')
            except DeserializationException as e:
                return Response({'message': e.args}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({'message': e.args}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            customer = request.user.customer_profile
            customer.phone_number = phone_number or customer.phone_number
            customer.tax_number = tax_number or customer.tax_number
            customer.company_name = company_name or customer.company_name
            customer.customer_address = customer_address or customer.customer_address
            customer.customer_billing_address = customer_billing_address or customer.customer_billing_address
            customer.customer_address.save()
            customer.customer_billing_address.save()
            customer.save()

        if hasattr(request.user, 'worker_profile'):
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

            worker = request.user.worker_profile
            worker.iban = iban or worker.iban
            worker.ssn = ssn or worker.ssn
            worker.worker_address = worker_address or worker.worker_address
            worker.date_of_birth = date_of_birth or worker.date_of_birth
            worker.place_of_birth = place_of_birth or worker.place_of_birth
            worker.accepted = accepted if accepted is not None else worker.accepted
            worker.hours = hours or worker.hours
            worker.worker_address.save()
            worker.save()

        if hasattr(request.user, 'admin_profile'):
            try:
                session_duration = formatter.get_value('session_duration')
            except DeserializationException as e:
                return Response({'message': e.args}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({'message': e.args}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            admin = request.user.admin_profile
            admin.session_duration = session_duration or admin.session_duration
            admin.save()

        request.user.save()

        return Response({'user_id': request.user.id})


class LanguageSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        languages = sorted(set(setting.language for setting in Settings.objects.all() if setting.language))
        return JsonResponse({'languages': languages})

    def put(self, request):
        formatter = FormattingUtil(data=request.data)

        try:
            language = formatter.get_value('language', required=True)
        except DeserializationException as e:
            return Response({'message': e.args}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'message': e.args}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if language:
            settings = request.user.settings or Settings.objects.create(language=language)
            settings.language = language
            settings.save()
            request.user.settings = settings
            request.user.save()

        return Response({'language': request.user.settings.language})


class UploadUserProfilePictureView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = get_object_or_404(User, id=kwargs['id'])
        profile_picture_url = user.profile_picture.url if user.profile_picture else None
        return Response({'profile_picture': profile_picture_url})

    def put(self, request, *args, **kwargs):
        user = get_object_or_404(User, id=kwargs['id'])

        if not request.data:
            return HttpResponseBadRequest()

        user.profile_picture = next(iter(request.data.values()))
        user.save()

        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetRequestView(APIView):
    """
    Password reset request view
    """

    def post(self, request, *args, **kwargs):
        """
        POST method handler
        """
        formatter = FormattingUtil(data=request.data)

        try:
            email = formatter.get_email(k_email, required=True)
        except Exception as e:
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({k_message: 'Email not found.'}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

        pass_reset_util = CustomPasswordResetUtil()
        pass_reset_util.send_reset_code(user)

        return Response({k_message: 'Password reset email has been sent.'}, status=HTTPStatus.OK)


class VerifyCodeView(APIView):
    """
    Verify code view
    """

    def post(self, request, *args, **kwargs):
        """
        POST method handler
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


class ResetPasswordView(APIView):
    """
    Reset password view
    """

    def post(self, request, *args, **kwargs):
        """
        POST method handler
        """
        formatter = FormattingUtil(data=request.data)

        try:
            token = formatter.get_value(k_token, required=True)
            code = formatter.get_value(k_code, required=True)
            password = formatter.get_value(k_password, required=True)
        except Exception as e:
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)

        pass_reset_util = CustomPasswordResetUtil()
        user = pass_reset_util.get_user_by_token_and_code(token, code)
        if user:
            password = EncryptionUtil.encrypt(password)
            user.password = password
            user.save()

            return Response({k_message: 'Password has been reset.'}, status=HTTPStatus.OK)
        else:
            return Response({k_message: 'Invalid or expired token'}, status=HTTPStatus.BAD_REQUEST)


class BaseClientView(APIView):
    """
    Base view for authentication using only the client secret
    """

    permission_classes = []

    group = None

    # Override this to allow different groups.
    groups = [
        CUSTOMERS_GROUP_NAME,
        WORKERS_GROUP_NAME,
        CMS_GROUP_NAME,
    ]
    allowed_methods = ['GET', 'POST', 'UPDATE', 'DELETE', 'OPTIONS']

    def options(self, request, **kwargs):
        response = HttpResponse()
        response['allow'] = ','.join(self.allowed_methods)
        return response

    def dispatch(self, request: HttpRequest, *args, **kwargs):
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
        Returns the id of the created user if valid
        """

        formatter = FormattingUtil(data=request.data)

        # Required fields
        try:
            first_name = formatter.get_value(k_first_name, required=True)
            last_name = formatter.get_value(k_last_name, required=True)
            email = formatter.get_email(k_email, required=True)
            password = formatter.get_value(k_password, required=True)
            phone_number = formatter.get_value(k_phone_number, required=False)
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
        password = EncryptionUtil.encrypt(password)

        # Create the user with the encrypted password
        user = User(
            username=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            email=email,
            phone_number=phone_number,
        )

        # Use the manager to create the user
        UserManager.create_user(user)

        # Create the worker profile
        UserManager.create_worker_profile(
            user=user,
            iban=iban,
            ssn=ssn,
            worker_address=worker_address,
            date_of_birth=date_of_birth,
            place_of_birth=place_of_birth,
        )

        # Get the workers group
        group = Group.objects.get(name=WORKERS_GROUP_NAME)

        # Add user to group
        group.user_set.add(user)

        # Save the group
        group.save()

        # Returns the user's id
        return Response({k_id: user.id})


class StatisticsView(JWTBaseAuthView):
    groups = [
        WORKERS_GROUP_NAME,
    ]

    def post(self, request: HttpRequest):
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

    A view for getting worker details
    """

    # Overrides the app types with access to this view
    app_types = [
        CMS_GROUP_NAME,
    ]

    def get(self, request: HttpRequest, *args, **kwargs):
        try:
            worker = User.objects.get(id=kwargs['id'], groups__name__contains=WORKERS_GROUP_NAME, )
        except Job.DoesNotExist:
            return HttpResponseNotFound()

        return Response(data=WorkerUtil.to_worker_view(worker))

    def delete(self, request: HttpRequest, *args, **kwargs):
        try:
            worker = User.objects.get(id=kwargs['id'], groups__name__contains=WORKERS_GROUP_NAME, )
        except Job.DoesNotExist:
            return HttpResponseNotFound()

        my_group = Group.objects.get(name=WORKERS_GROUP_NAME)
        my_group.user_set.remove(worker)

        my_group.save()

        return Response()

    def put(self, request: HttpRequest, *args, **kwargs):
        try:
            worker = User.objects.get(id=kwargs['id'], groups__name__contains=WORKERS_GROUP_NAME, )
        except User.DoesNotExist:
            return HttpResponseNotFound()

        formatter = FormattingUtil(data=request.data)

        try:
            first_name = formatter.get_value(k_first_name)
            last_name = formatter.get_value(k_last_name)
            phone_number = formatter.get_value(k_phone_number)
            email = formatter.get_email(k_email)
            address = formatter.get_address(k_address)
            date_of_birth = formatter.get_date(k_date_of_birth)
            billing_address = formatter.get_address(k_billing_address)
            tax_number = formatter.get_value(k_tax_number)
            company = formatter.get_value(k_company)

        except DeserializationException as e:
            # If the inner validation fails, this throws an error
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            # Unhandled exception
            return Response({k_message: e.args}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

        worker.first_name = first_name or worker.first_name
        worker.last_name = last_name or worker.last_name
        worker.email = email or worker.email
        worker.phone_number = phone_number or worker.phone_number
        worker.worker_address = address or worker.workder_address
        worker.tax_number = tax_number or worker.tax_number
        worker.company_name = company or worker.company_name
        worker.date_of_birth = date_of_birth or worker.date_of_birth

        if address:
            address.save()
        if billing_address:
            billing_address.save()

        worker.save()

        return Response()


class WorkersListView(JWTBaseAuthView):
    """
    [CMS]

    GET

    View for CMS users to get workers details
    """

    # Overrides the app types with access to this view
    app_types = [
        CMS_GROUP_NAME,
    ]

    def get(self, request: HttpRequest, *args, **kwargs):
        item_count = 25
        page = 1
        search_term = None
        sort_term = None
        algorithm = None
        state = None

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
        try:
            search_term = kwargs['search_term']
        except KeyError:
            pass
        try:
            state = kwargs['state']
        except KeyError:
            pass

        block_unaccepted_workers = True

        if state == 'registered':
            block_unaccepted_workers = False

        if sort_term is not None:
            if algorithm == 'descending':
                sort_term = '-{}'.format(sort_term)

            workers = User.objects.filter(groups__name__contains=WORKERS_GROUP_NAME, archived=False,
                                          accepted=block_unaccepted_workers).order_by(
                sort_term)

        else:
            workers = User.objects.filter(groups__name__contains=WORKERS_GROUP_NAME, archived=False,
                                          accepted=block_unaccepted_workers)

        if search_term:
            first_name_query = workers.filter(first_name__icontains=search_term, )[:10]
            last_name_query = workers.filter(last_name__icontains=search_term, )[:10]
            email_query = workers.filter(email__icontains=search_term, )[:10]

            data = []

            for query in [first_name_query, last_name_query, email_query]:
                for worker in query:
                    data.append(worker)

            paginator = Paginator(data, per_page=item_count, )

            response_data = []

            workers = []

            for worker in paginator.page(page).object_list:
                if worker in workers:
                    continue
                workers.append(worker)
                response_data.append(WorkerUtil.to_worker_view(worker))

            return Response({k_workers: response_data, k_items_per_page: paginator.per_page, k_total: len(
                data)})

        paginator = Paginator(workers, per_page=item_count)

        data = []

        for worker in paginator.page(page).object_list:
            data.append(WorkerUtil.to_worker_view(worker))

        # Return the worker id
        return Response({k_workers: data, k_items_per_page: paginator.per_page, k_total: len(
            workers)})


class AcceptWorkerView(JWTBaseAuthView):
    """
    [ALL]

    GET

    A view for getting worker details
    """

    # Overrides the app types with access to this view
    app_types = [
        CMS_GROUP_NAME,
    ]

    def post(self, request: HttpRequest, *args, **kwargs):
        try:
            worker = User.objects.get(id=kwargs['id'], groups__name__contains=WORKERS_GROUP_NAME, )
        except User.DoesNotExist:
            return HttpResponseNotFound()

        worker.accepted = True

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
        formatter = FormattingUtil(data=request.data)

        try:
            first_name = formatter.get_value(k_first_name, required=True)
            last_name = formatter.get_value(k_last_name, required=True)
            email = formatter.get_email(k_email, required=True)

            # Optional fields
            address = formatter.get_address(k_address)
            billing_address = formatter.get_address(k_billing_address)
            tax_number = formatter.get_value(k_tax_number)
            company = formatter.get_value(k_company)
            phone_number = formatter.get_value(k_phone_number)
        except DeserializationException as e:
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            return Response({k_message: e.args}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

        if address:
            address.save()
        if billing_address:
            billing_address.save()

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': email,
                'first_name': first_name,
                'last_name': last_name,
            }
        )

        if not created:
            if not user.groups.filter(name=CUSTOMERS_GROUP_NAME).exists():
                my_group = Group.objects.get(name=CUSTOMERS_GROUP_NAME)
                my_group.user_set.add(user)

            user.archived = False
            user.first_name = first_name or user.first_name
            user.last_name = last_name or user.last_name
            user.save()

        UserManager.create_customer_profile(
            user=user,
            phone_number=phone_number,
            tax_number=tax_number,
            company_name=company,
            customer_address=address,
            customer_billing_address=billing_address
        )

        if created:
            my_group = Group.objects.get(name=CUSTOMERS_GROUP_NAME)
            my_group.user_set.add(user)
            my_group.save()

        return Response({k_customer_id: user.id})


class CustomersListView(JWTBaseAuthView):
    """
    [CMS]

    GET

    View for CMS users to get customer details
    """

    # Overrides the app types with access to this view
    app_types = [
        CMS_GROUP_NAME,
    ]

    def get(self, request: HttpRequest, *args, **kwargs):
        item_count = kwargs.get('count', 25)
        page = kwargs.get('page', 1)
        search_term = kwargs.get('search_term')
        sort_term = kwargs.get('sort_term')
        algorithm = kwargs.get('algorithm')

        active_job_customers = Job.objects.filter(
            start_time__lt=datetime.datetime.utcnow(),
            job_state=JobState.pending
        ).values_list('customer', flat=True)

        customers = User.objects.filter(
            groups__name__contains=CUSTOMERS_GROUP_NAME,
            archived=False
        )

        if sort_term:
            if algorithm == 'descending':
                sort_term = f'-{sort_term}'
            customers = customers.order_by(sort_term)

        if search_term:
            queries = [
                customers.filter(first_name__icontains=search_term)[:10],
                customers.filter(last_name__icontains=search_term)[:10],
                customers.filter(email__icontains=search_term)[:10]
            ]
            data = list({customer for query in queries for customer in query})
        else:
            data = list(customers)

        paginator = Paginator(data, per_page=item_count)
        paginated_customers = paginator.page(page).object_list

        response_data = [
            CustomerUtil.to_customer_view(customer, has_active_job=customer.id in active_job_customers)
            for customer in paginated_customers
        ]

        return Response({
            k_customers: response_data,
            k_items_per_page: paginator.per_page,
            k_total: paginator.count
        })


class CustomerDetailView(JWTBaseAuthView):
    """
    [ALL]

    GET

    A view for getting customer details
    """

    # Overrides the app types with access to this view
    app_types = [
        CMS_GROUP_NAME,
    ]

    def get(self, request: HttpRequest, *args, **kwargs):
        try:
            customer = User.objects.get(id=kwargs['id'], groups__name__contains=CUSTOMERS_GROUP_NAME)
        except User.DoesNotExist:
            return HttpResponseNotFound()

        return Response(data=CustomerUtil.to_customer_view(customer))

    def delete(self, request: HttpRequest, *args, **kwargs):
        try:
            customer = User.objects.get(id=kwargs['id'], groups__name__contains=CUSTOMERS_GROUP_NAME)
        except User.DoesNotExist:
            return HttpResponseNotFound()

        my_group = Group.objects.get(name=CUSTOMERS_GROUP_NAME)
        my_group.user_set.remove(customer)

        my_group.save()

        return Response()

    def put(self, request: HttpRequest, *args, **kwargs):
        try:
            customer = User.objects.get(id=kwargs['id'], groups__name__contains=CUSTOMERS_GROUP_NAME)
        except User.DoesNotExist:
            return HttpResponseNotFound()

        formatter = FormattingUtil(data=request.data)

        try:
            first_name = formatter.get_value('first_name')
            last_name = formatter.get_value('last_name')
            email = formatter.get_email('email')
            phone_number = formatter.get_value('phone_number')
            address = formatter.get_address('address')
            billing_address = formatter.get_address('billing_address')
            tax_number = formatter.get_value('tax_number')
            company = formatter.get_value('company')
        except DeserializationException as e:
            return Response({'message': e.args}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            return Response({'message': e.args}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

        customer.first_name = first_name or customer.first_name
        customer.last_name = last_name or customer.last_name
        customer.email = email or customer.email

        customer_profile = customer.customer_profile
        customer_profile.phone_number = phone_number or customer_profile.phone_number
        customer_profile.customer_address = address or customer_profile.customer_address
        customer_profile.customer_billing_address = billing_address or customer_profile.customer_billing_address
        customer_profile.tax_number = tax_number or customer_profile.tax_number
        customer_profile.company_name = company or customer_profile.company_name

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

    View for CMS users to get customer details based on search terms
    """

    # Overrides the app types with access to this view
    app_types = [
        CMS_GROUP_NAME,
    ]

    def get(self, request: HttpRequest, *args, **kwargs):
        search_term = kwargs.get('search_term')
        if not search_term:
            return HttpResponseNotFound()

        customers = User.objects.filter(groups__name__contains=CUSTOMERS_GROUP_NAME)
        queries = [
            customers.filter(first_name__icontains=search_term)[:5],
            customers.filter(last_name__icontains=search_term)[:5],
            customers.filter(email__icontains=search_term)[:5]
        ]

        data = {CustomerUtil.to_customer_view(customer) for query in queries for customer in query}

        return Response({k_customers: list(data)})
