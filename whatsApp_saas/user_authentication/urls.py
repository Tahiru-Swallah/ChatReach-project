from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import home, CustomTokenObtainPairView, registration, loginForm, registerForm, logout, GoogleLoginAPI

app_name = 'user_authentication'

urlpatterns = [
    path('', home, name='home'),

    #GOOGLE LOGIN API
    path('google/', GoogleLoginAPI.as_view(), name='google'),

    #LOGIN APIs URLs
    path('api/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    #REGISTER APIs URL
    path('api/register/', registration, name='register'),

    #LOGOUT API
    path('api/logout/', logout, name='logout'),

    #TEMPLATE URLS FOR CONSUMING THE ABOVE APIs
    path('login/', loginForm, name='login'),
    path('register/', registerForm, name='register'),
]
