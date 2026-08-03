from django.urls import path
from . import views
from rest_framework.routers import DefaultRouter

from user_authentication.views import home

app_name = 'user_business'

router = DefaultRouter()
router.register(r'api/templates', views.WhatsAppTemplateViewSet, basename='whatsapptemplate')

urlpatterns = [
    path('', home, name='home'),
    
    # Search, filter, list, and single contact creation
    path('api/contacts/', views.customer_contact_list_create_view, name='contact-list-create'),
    
    # Detail operations (get, update, delete single contact by ID)
    path('api/contacts/<uuid:pk>/', views.customer_contact_detail_view, name='contact-detail'),
    
    # File upload endpoint (CSV / Excel)
    path('api/contacts/upload/', views.upload_customer_contacts_view, name='contact-file-upload'),

    # Dispatch Template
    path('api/send-template-campaign/', views.send_template_campaign, name='send-template-campaign'),

    #TEMPLATE OF CONSUMING APIs NOW
    path('contact/form/', views.contact_form, name='contact_form'),
    path('schedule/message/', views.schedule_form, name='schedule_message_form'),
    path('template/form/', views.template_form, name='template_form'),
] 

urlpatterns += router.urls
