from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.http import JsonResponse, HttpResponseNotFound, HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from .models import User
from apps.core.models.settings import Settings
from apps.core.model_exceptions import DeserializationException
from apps.core.utils.formatters import FormattingUtil
from apps.core.utils.profile import ProfileUtil
from apps.core.utils.wire_names import k_token, k_code, k_password, k_message, k_email
from http import HTTPStatus
from apps.authentication.utils.pass_reset_util import CustomPasswordResetUtil
from apps.authentication.utils.encryption_util import EncryptionUtil


class JWTAuthenticationView(TokenObtainPairView):
    pass


class JWTRefreshView(TokenRefreshView):
    pass


class JWTTestConnectionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"message": "Connection successful"})


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
