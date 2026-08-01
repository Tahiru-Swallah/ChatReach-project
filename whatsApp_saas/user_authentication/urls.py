from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

#from .views import home, CustomTokenObtainPairView, registration, loginForm, registerForm, logout, GoogleLoginAPI
from . import views

app_name = 'user_authentication'

urlpatterns = [
    #GOOGLE LOGIN API
    path('google/', views.GoogleLoginAPI.as_view(), name='google'),

    #LOGIN APIs URLs
    path('api/login/', views.CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    #REGISTER APIs URL
    path('api/register/', views.registration, name='register'),

    #LOGOUT API
    path('api/logout/', views.logout, name='logout'),

    #TEMPLATE URLS FOR CONSUMING THE ABOVE APIs
    path('login/', views.loginForm, name='login'),

    path('business/profile/', views.business_profile_form, name='business_profile'),
    path('api/business/profile/create/', views.create_business_profile),

    path('api/whatsapp/send-message/', views.sendWhatsAppMessage, name='send_whatsApp_message'),

    path('api/whatsapp/exchange-code/', views.exchange_code_for_access_token, name='exchange_code_for_access_token'),

    path('api/whatsapp/webhook/', views.whatsApp_webhook, name='whatsapp_webhook'),

    path('send_catalog/', views.send_catalog, name="send_catalog"),

    path('api/products/', views.product_list_or_create),

    path('api/catalog/sync/', views.sync_business_products_to_catalog),
]
