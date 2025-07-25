from django.shortcuts import render
from django.contrib.auth.decorators import login_required 
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

# REST FRAMEWORK LIBRARIES
from rest_framework.views import APIView
from rest_framework.decorators import api_view, authentication_classes, permission_classes, parser_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

# LOCAL LIBRARIES
from .models import CustomUser, BusinessProfile
from .serializer import CustomTokenObtainPairSerializer, RegisterSerializer, BusinessProfileSerializer

# GOOGLE AUTH LIBRARIES
from dj_rest_auth.registration.views import SocialLoginView
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_or_update_business_profile(request):
    try:
        profile = BusinessProfile.objects.get(user=request.user)
        serializer = BusinessProfileSerializer(profile, data=request.data, partial=True, context = {'request': request})
    
    except BusinessProfile.DoesNotExist:
        serializer = BusinessProfileSerializer(data=request.data, context = {'request': request})

    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_business_profile(request):
    try:
        profile = BusinessProfile.objects.get(user=request.user)
        serializer = BusinessProfileSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    except BusinessProfile.DoesNotExist:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class GoogleLoginAPI(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter

    def post(self, request, *args, **kwargs):
        id_token = request.data.get('id_token')

        if not id_token:
            return Response({'detail': 'Missing ID token'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            from google.oauth2 import id_token as google_id_token
            from google.auth.transport import requests

            id_info = google_id_token.verify_oauth2_token(
                id_token,
                requests.Request(),
                settings.GOOGLE_SOCIAL_AUTH_ID
            )

            email = id_info['email']
            name = id_info.get('name')

            user, create = CustomUser.objects.get_or_create(email=email)

            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)

            response = Response({
                'access_token': access_token,
                'refresh_token': str(refresh)
            })

            response.set_cookie(
                'access_token',
                access_token,
                httponly=True,
                secure=False,  # Change to True in production (with HTTPS)
                samesite='Lax',
                max_age=3600
            )

            return response
        
        except ValueError:
            return Response({'detail': 'Invalid google token'}, status=status.HTTP_400_BAD_REQUEST)


# TEMPLATE FOR CONSUMING BELOW APIs
def loginForm(request):
    context = {'GOOGLE_AUTH_CLIENT_ID' : settings.GOOGLE_SOCIAL_AUTH_ID}
    return render(request, 'registration/login.html', context)

def registerForm(request):
    return render(request, 'registration/register.html')

@login_required
def home(request):
    return render(request, 'home.html', {})

@login_required
def business_profile_form(request):
    return render(request,'whatsapp/profile.html', {})

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        data = serializer.validated_data
        response = Response(data, status=status.HTTP_200_OK)
        response.set_cookie(
            'access_token',
            data.get("access_token"),
            httponly=True,
            secure=False, # Set to True if you're using HTTPS
            max_age=3600, 
            samesite='Lax'
        )

        return response

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@csrf_exempt   
def registration(request):
    serializer = RegisterSerializer(data=request.data)

    if serializer.is_valid():
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        response = Response(
            {
                'message': 'User Login successfully',
                'refresh_token': str(refresh),
                'access_token': access_token,
                'user': RegisterSerializer(instance=user).data
            }, 
            status=status.HTTP_200_OK
        )

        response.set_cookie(
            'access_token',
            access_token,
            httponly=True,
            secure=False, # Set to True if you're using HTTPS
            samesite='Lax'
        )

        return response
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    refresh_token = request.data.get('refresh_token')

    if refresh_token:
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    response = Response({"message": 'Logout Successful'}, status=status.HTTP_200_OK)
    response.delete_cookie('access_token')

    return response