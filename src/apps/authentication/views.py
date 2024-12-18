from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.http import JsonResponse, HttpResponseNotFound, HttpResponseBadRequest
from .models import User
from apps.core.models.settings import Settings
from apps.core.model_exceptions import DeserializationException
from apps.core.utils.formatters import FormattingUtil
from apps.core.utils.profile import ProfileUtil


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
        try:
            profile_picture = ProfileUtil.get_user_profile_picture_url(request.user)
        except ValueError:
            profile_picture = None

        data = {
            'user_id': request.user.id,
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
            'date_of_birth': FormattingUtil.to_timestamp(request.user.date_of_birth),
            'phone_number': request.user.phone_number,
            'description': request.user.description,
            'profile_picture': profile_picture,
        }

        try:
            data['address'] = request.user.address.to_model_view()
        except Exception:
            pass
        try:
            data['language'] = Settings.objects.get(id=request.user.settings_id).language
        except Exception:
            pass

        return Response(data)

    def post(self, request):
        formatter = FormattingUtil(data=request.data)

        try:
            first_name = formatter.get_value('first_name')
            last_name = formatter.get_value('last_name')
            email = formatter.get_email('email')
            tax_number = formatter.get_value('tax_number')
            date_of_birth = formatter.get_date('date_of_birth')
            phone_number = formatter.get_value('phone_number')
            address = formatter.get_address('address')
            billing_address = formatter.get_address('billing_address')
        except DeserializationException as e:
            return Response({'message': e.args}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'message': e.args}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if first_name is not None:
            request.user.first_name = first_name
        if last_name is not None:
            request.user.last_name = last_name
        if email is not None:
            request.user.email = email
        if tax_number is not None:
            request.user.tax_number = tax_number
        if date_of_birth is not None:
            request.user.date_of_birth = date_of_birth
        if phone_number is not None:
            request.user.phone_number = phone_number
        if address is not None:
            address.save()
            request.user.address = address
        if billing_address is not None:
            billing_address.save()
            request.user.billing_address = billing_address

        request.user.save()

        return Response({'user_id': request.user.id})


class LanguageSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        settings = Settings.objects.all()
        languages = [setting.language for setting in settings if setting.language is not None]
        unique_languages = sorted(set(languages))
        return JsonResponse({'languages': unique_languages})

    def post(self, request):
        formatter = FormattingUtil(data=request.data)

        try:
            language = formatter.get_value('language', required=True)
        except DeserializationException as e:
            return Response({'message': e.args}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'message': e.args}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if language is not None:
            if request.user.settings:
                settings = request.user.settings
                settings.language = language
                settings.save()
            else:
                settings = Settings.objects.create(language=language)
                request.user.settings = settings

            request.user.save()

        return Response({'language': request.user.settings.language})


class UploadUserProfilePictureView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            user = User.objects.get(id=kwargs['id'])
        except User.DoesNotExist:
            return HttpResponseNotFound()

        if user.profile_picture:
            return Response({'profile_picture': user.profile_picture.url})
        else:
            return Response({'profile_picture': None})

    def put(self, request, *args, **kwargs):
        try:
            user = User.objects.get(id=kwargs['id'])
        except User.DoesNotExist:
            return HttpResponseNotFound()

        name = None
        for filename in request.data.keys():
            name = filename

        if name is None:
            return HttpResponseBadRequest()

        user.profile_picture = request.data[name]
        user.save()

        return Response(status=status.HTTP_204_NO_CONTENT)
