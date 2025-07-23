from django.shortcuts import render


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import CustomerContact, ScheduledMessage
from .serializer import CustomerContactSerializer, ScheduledMessageSerializer
import pandas as pd

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
    
    created, failed = [], []

    for _, row in df.iterrows():
        contact_data = {
            'name': row.get('name'),
            'phone_number': row.get('phone_number'),
            'email': row.get('email', ''),
            'tag': row.get('tag', ''),
        } 
    
    serializer = CustomerContactSerializer(data=contact_data, context = {'request': request})
    if serializer.is_valid():
        serializer.save()
        created.append(serializer.data)
    
    else:
        failed.append({'contact_data': contact_data, 'errors': serializer.errors})

    return Response({'created': created, 'failed': failed}, status=status.HTTP_207_MULTI_STATUS)


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
    serializer = ScheduledMessageSerializer(data=request.data, context={'request': request})

    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    
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