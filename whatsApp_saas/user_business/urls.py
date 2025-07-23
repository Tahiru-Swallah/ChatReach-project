from django.urls import path
from . import views

app_name = 'user_business'

urlpatterns = [
    # CONTACT CREATION AND LISTING API
    path('api/contacts/', views.list_customer_contacts, name='list_customer_contacts'),
    path('api/contacts/create/', views.create_customer_contact, name='create_customer_contact'),
    path('api/contacts/import-excel/', views.import_contacts_from_excel, name='import_contacts_excel'),

    #UPDATE AND DELETE CONTACT APIs
    path('api/contact/<uuid:pk>/edit/', views.update_customer_contacts, name='update_contacts'),
    path('api/contact/<uuid:pk>/delete/', views.delete_customer_contact, name='update_contacts'),

    #MESSAGE SCHEDULE APIs
    path('api/schedule/message/create/', views.schedule_message, name='schedule_message'),
    path('api/schedule/messages/', views.list_schedule_messages, name="list_schedule_messages"),
    path('api/schedule/<uuid:message_id>/edit/', views.update_schedule_message, name='update_schedule_message'),
    path('api/schedule/<uuid:message_id>/delete/', views.delete_scheduled_message, name='delete_schedule_message'),

    #MESSAGE TEMPLATE CATEGORIES AND TEMPLATE APIs
    path('api/category/create/', views.create_and_list_template_category, name='category'),
    path('api/message/template/create/', views.create_list_message_template, name='template'),
    path('api/message/<uuid:pk>/edit/delete/', views.edit_delete_message_template, name='message_template')
]
