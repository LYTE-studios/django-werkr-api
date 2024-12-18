from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


class JWTAuthenticationView(TokenObtainPairView):
    pass


class JWTRefreshView(TokenRefreshView):
    pass


class JWTTestConnectionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"message": "Connection successful"})
