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
        profile_picture = ProfileUtil.get_user_profile_picture_url(request.user) if ProfileUtil.get_user_profile_picture_url(request.user) else None

        data = {
            'user_id': request.user.id,
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
            'date_of_birth': FormattingUtil.to_timestamp(request.user.date_of_birth),
            'phone_number': request.user.phone_number,
            'description': request.user.description,
            'profile_picture': profile_picture,
            'address': getattr(request.user.address, 'to_model_view', lambda: None)(),
            'language': getattr(Settings.objects.filter(id=request.user.settings_id).first(), 'language', None)
        }

        return Response(data)

    def put(self, request):
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

        request.user.first_name = first_name
        request.user.last_name = last_name
        request.user.email = email
        request.user.tax_number = tax_number
        request.user.date_of_birth = date_of_birth
        request.user.phone_number = phone_number
        address.save()
        request.user.address = address
        billing_address.save()
        request.user.billing_address = billing_address

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