from django.shortcuts import render
from django.contrib.auth.decorators import login_required
import phonenumbers
from django.db import IntegrityError

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import CustomerContact, ScheduledMessage, TemplateCategory, MessageTemplate
from .serializer import CustomerContactSerializer, ScheduledMessageSerializer, MessageTemplateSerializer, TemplateCategorySerializer
import pandas as pd
from .utils import send_whatsapp_message


@login_required
def contact_form(request):
    return render(request, 'business/contact_form.html', {})

@login_required
def schedule_form(request):
    return render(request, 'business/schedule_form.html', {})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_customer_contact(request):
    serializer = CustomerContactSerializer(data=request.data, context={'request': request})

    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_customer_contacts(request):
    contacts = CustomerContact.objects.filter(user=request.user)
    serializer = CustomerContactSerializer(contacts, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

def clean_phone_number(number, region='GH'):
    try:
        parsed = phonenumbers.parse(str(number), region)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except Exception:
        return None
    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def import_contacts_from_excel(request):
    file = request.FILES.get('file')

    if not file:
        return Response({'error': 'Excel file required (.xlsx).'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        df = pd.read_excel(file)
    except Exception as e:
        return Response({'error': f'Failed to read Excel file: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
    
    required_columns = {'name', 'phone_number'}

    if not required_columns.issubset(set(df.columns)):
        return Response(
            {
                'error': 'Excel must contain at least "name" and "phone_number" columns.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    df.fillna('', inplace=True)

    created, failed, skip_duplicates = [], [], []
    existing_numbers = set(
        CustomerContact.objects.filter(user=request.user).values_list('phone_number', flat=True)
    )

    for _, row in df.iterrows():
        raw_number = row.get('phone_number')
        cleaned_number = clean_phone_number(raw_number)

        if not cleaned_number:
            failed.append({'contact_data': row.to_dict(), 'errors': 'Invalid phone number format'})
            continue
            
        if cleaned_number in existing_numbers:
            skip_duplicates.append({'contact_data': row.to_dict(), 'errors': 'Contact already exists'})
            continue
            
        contact_data = {
            'name': row.get('name'),
            'phone_number': cleaned_number,
            'email': row.get('email', ''),
            'tag': row.get('tag', ''),
        } 
    
        serializer = CustomerContactSerializer(data=contact_data, context = {'request': request})
        if serializer.is_valid():
            try:
                serializer.save()
                created.append(serializer.data)
                existing_numbers.add(cleaned_number)

            except IntegrityError:
                skip_duplicates.append({'contact_data': row.to_dict(), 'reason': 'Duplicate phone number (caught during save)'})
        else:
            failed.append({'contact_data': contact_data, 'errors': serializer.errors})

    return Response({'created': created, 'failed': failed, 'skip_duplicates': skip_duplicates}, status=status.HTTP_207_MULTI_STATUS)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_customer_contacts(request, pk):
    try:
        contact = CustomerContact.objects.get(pk=pk, user=request.user)
    except CustomerContact.DoesNotExist:
        return Response({'error': 'Contact not found'}, status=status.HTTP_404_NOT_FOUND)
    
    serializer = CustomerContactSerializer(contact, data=request.data, context={'request': request})
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_customer_contact(request, pk):
    try:
        contact = CustomerContact.objects.get(pk=pk, user=request.user)
    except CustomerContact.DoesNotExist:
        return Response({'error': 'Contact not found'}, status=status.HTTP_404_NOT_FOUND)

    contact.delete()
    return Response({'message': 'Contact deleted successfully'}, status=status.HTTP_204_NO_CONTENT)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def schedule_message(request):
    print("Incoming Data:", dict(request.data))
    print("FILES:", request.FILES)

    serializer = ScheduledMessageSerializer(data=request.data, context={'request': request})

    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    print("Serializer Errors:", serializer.errors)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_schedule_messages(request):
    messages = ScheduledMessage.objects.filter(user=request.user).order_by('-scheduled_time')
    serializer = ScheduledMessageSerializer(messages, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_schedule_message(request, message_id):
    try:
        message = ScheduledMessage.objects.get(id=message_id, user=request.user)
    except ScheduledMessage.DoesNotExist:
        return Response({'error': 'Scheduled message not found.'}, status=status.HTTP_404_NOT_FOUND)
    
    serializer = ScheduledMessageSerializer(message, data=request.data, partial=True, context={'request': request})

    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_scheduled_message(request, message_id):
    try:
        message = ScheduledMessage.objects.get(id=message_id, user=request.user)
        message.delete()
        return Response({'message': 'Scheduled message deleted successfully.'}, status=status.HTTP_204_NO_CONTENT)
    except ScheduledMessage.DoesNotExist:
        return Response({'error': 'Scheduled message not found.'}, status=status.HTTP_404_NOT_FOUND)
    
@api_view(['POST', 'GET'])
@permission_classes([IsAuthenticated])
def create_and_list_template_category(request):
    if request.method == 'GET':
        categories = TemplateCategory.objects.filter(user=request.user)
        serializer = TemplateCategorySerializer(categories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = TemplateCategorySerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST', 'GET'])
@permission_classes([IsAuthenticated])
def create_list_message_template(request):
    if request.method == 'GET':
        message_template = MessageTemplate.objects.filter(user=request.user)
        serializer = MessageTemplateSerializer(message_template, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = MessageTemplateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def edit_delete_message_template(request, pk):
    try:
        message = MessageTemplate.objects.get(pk=pk, user =request.user)
    except MessageTemplate.DoesNotExist:
        return Response({'detail': 'Message template does not exist'}, status=status.HTTP_400_BAD_REQUEST0)
    
    if request.method == 'PUT':
        serializer = MessageTemplateSerializer(message, data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_200_OK)
    
    elif request.method == 'DELETE':
        message.delete()
        return Response({'detail': 'Message template deleted successfully'}, status=status.HTTP_204_NO_CONTENT)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_template_message(request):
    template_id = request.data.get('template_id')
    contact_ids = request.data.get('contact_ids')

    if not template_id and not contact_ids:
        return Response({'error': 'Temaplate_Id and contact_id are required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        template = MessageTemplate.objects.get(id=template_id, user=request.user)
        contacts = CustomerContact.objects.filter(id__in=contact_ids, user=request.user)

        success = []
        failed = []

        for contact in contacts:
            try:
                send_whatsapp_message(
                    phone_number=contact.phone_number,
                    message_text=template,
                )
                success.append(contact.phone_number)

            except Exception as e:
                failed.append({
                    "phone": contact.phone_number,
                    "error": str(e)
                })

        return Response({
            "message": "Message processing completed",
            "success": success,
            "failed": failed
        }, status=status.HTTP_200_OK)
    
    except MessageTemplate.DoesNotExist:
        return Response({'error': 'Template does not exist'}, status=status.HTTP_404_NOT_FOUND)
    
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)