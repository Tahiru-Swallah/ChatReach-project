from django.shortcuts import render
from django.contrib.auth.decorators import login_required
import phonenumbers
from django.db import IntegrityError

from rest_framework.decorators import api_view, permission_classes, parser_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework import status, viewsets

from .models import CustomerContact, WhatsAppTemplate
from .serializer import CustomerContactSerializer, BulkCustomerContactSerializer, WhatsAppTemplateSerializer

from user_authentication.models import WhatsAppConnection

import pandas as pd
import re
from .utils import push_template_to_meta, fetch_remote_templates_status

from django.db.models import Q
from django.conf import settings
import requests


@login_required
def contact_form(request):
    return render(request, 'business/contact_form.html', {})

@login_required
def schedule_form(request):
    return render(request, 'business/schedule_form.html', {})

@login_required
def template_form(request):
    return render(request, 'business/template_form.html', {})

@api_view(['POST', 'GET'])
@permission_classes([IsAuthenticated])
def customer_contact_list_create_view(request):
    """
    Handles listing, searching, filtering, and creating customer contacts.
    Supports both single contact creation and bulk uploads.
    """

    business = request.user.owned_businesses.first()
    if not business:
        return Response(
            {"error": "No business associated with this account."},
            status=status.HTTP_400_BAD_REQUEST
        )

    if request.method == 'GET':
        search_query = request.GET.get('search', '')
        tag_filter = request.GET.get('tag', '')

        contacts = CustomerContact.objects.filter(business=business)

        if search_query:
            contacts = contacts.filter(
                Q(name__icontains=search_query) |
                Q(phone_number__icontains=search_query) |
                Q(email__icontains=search_query)
            )

        if tag_filter:
            contacts = contacts.filter(tag__contains=[tag_filter])

        opt_in = request.query_params.get('opt_in', None)
        if opt_in is not None:
            is_opted_in = opt_in.lower() in ['true', '1']
            contacts = contacts.filter(is_opted_in=is_opted_in)

        serializer = CustomerContactSerializer(contacts, many=True, context={'request': request})
        return Response(
            {
                "total_count": contacts.count(),
                "results": serializer.data
            },
            status=status.HTTP_200_OK
        )

    elif request.method == 'POST':
        # Check if the payload is a bulk import (contains a "contacts" list key)

        if 'contacts' in request.data and isinstance(request.data['contacts'], list):
            serializer = BulkCustomerContactSerializer(data=request.data, context={'request': request})
            if serializer.is_valid():
                result = serializer.save()
                return Response(result, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer = CustomerContactSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Contact created successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def customer_contact_detail_view(request, pk):
    """
    Handles retrieving, updating, and deleting an individual contact by ID.
    """
    business = request.user.owned_businesses.first()
    if not business:
        return Response(
            {"error": "No business associated with this account."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Scoped directly to business tenant for security
    try:
        contact = CustomerContact.objects.get(pk=pk, business=business)
    except CustomerContact.DoesNotExist:
        return Response(
            {"error": "Contact not found."},
            status=status.HTTP_404_NOT_FOUND
        )

    if request.method == 'GET':
        serializer = CustomerContactSerializer(contact)
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method in ['PUT', 'PATCH']:
        partial = (request.method == 'PATCH')
        serializer = CustomerContactSerializer(
            contact,
            data=request.data,
            partial=partial,
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "message": "Contact updated successfully.",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        contact.delete()
        return Response(
            {"message": "Contact deleted successfully."},
            status=status.HTTP_204_NO_CONTENT
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_customer_contacts_view(request):
    """
    Handles file uploads (.csv, .xlsx, .xls) and bulk-creates/updates contacts.
    Expects form-data with key 'file'.
    """
    business = request.user.owned_businesses.first()
    if not business:
        return Response(
            {"error": "No business associated with this account."},
            status=status.HTTP_400_BAD_REQUEST
        )

    file_obj = request.FILES.get('file')
    if not file_obj:
        return Response(
            {"error": "No file uploaded. Please select a .csv or .xlsx file."},
            status=status.HTTP_400_BAD_REQUEST
        )

    file_name = file_obj.name.lower()

    # Parse file into a Pandas DataFrame based on file extension
    try:
        if file_name.endswith('.csv'):
            df = pd.read_csv(file_obj, dtype=str)  # Read all columns as string
        elif file_name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file_obj, dtype=str)
        else:
            return Response(
                {"error": "Unsupported file format. Please upload a .csv or .xlsx file."},
                status=status.HTTP_400_BAD_REQUEST
            )
    except Exception as e:
        return Response(
            {"error": f"Failed to parse file: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Normalize column headers to lowercase & strip whitespace
    df.columns = [str(col).strip().lower() for col in df.columns]

    # Flexible Column Mapping (Finds matching columns regardless of capitalization or slight variation)
    phone_col = next((c for c in df.columns if 'phone' in c or 'mobile' in c or 'contact' in c), None)
    name_col = next((c for c in df.columns if 'name' in c or 'customer' in c), None)
    email_col = next((c for c in df.columns if 'email' in c or 'mail' in c), None)
    tag_col = next((c for c in df.columns if 'tag' in c or 'category' in c or 'group' in c), None)

    if not phone_col:
        return Response(
            {"error": "Could not identify a phone number column in your spreadsheet. Please ensure a column named 'phone' or 'mobile' exists."},
            status=status.HTTP_400_BAD_REQUEST
        )

    created_count = 0
    updated_count = 0
    skipped_count = 0

    # Process each row
    for _, row in df.iterrows():
        raw_phone = str(row.get(phone_col, '')).strip()

        # Skip empty rows or nan values
        if not raw_phone or raw_phone.lower() in ['nan', 'none', 'null']:
            skipped_count += 1
            continue

        # Basic phone cleanup
        clean_phone = raw_phone.lstrip('+').split('.')[0]  # Remove trailing float .0 if present from Excel

        # Extract remaining fields
        name = str(row.get(name_col, '')).strip() if name_col and pd.notna(row.get(name_col)) else ''
        email = str(row.get(email_col, '')).strip() if email_col and pd.notna(row.get(email_col)) else None

        # Process Tags (Splits comma-separated tags e.g. "VIP, Kumasi, Wholesale" -> ["VIP", "Kumasi", "Wholesale"])
        raw_tags = str(row.get(tag_col, '')).strip() if tag_col and pd.notna(row.get(tag_col)) else ''
        tags_list = [t.strip() for t in raw_tags.split(',') if t.strip()] if raw_tags else []

        # Upsert into DB (Update if exists, Create if new)
        contact, created = CustomerContact.objects.update_or_create(
            business=business,
            phone_number=clean_phone,
            defaults={
                'name': name or None,
                'email': email or None,
                'tag': tags_list,
                'is_opted_in': True,
            }
        )

        if created:
            created_count += 1
        else:
            updated_count += 1

    return Response(
        {
            "message": "File processed successfully.",
            "summary": {
                "created": created_count,
                "updated": updated_count,
                "skipped": skipped_count,
                "total_rows": len(df)
            }
        },
        status=status.HTTP_200_OK
    )

class WhatsAppTemplateViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = WhatsAppTemplateSerializer

    def get_queryset(self):
        business = getattr(self.request.user, 'owned_businesses', None)
        business = business.first() if business else None

        if not business:
            return WhatsAppTemplate.objects.none()
        return WhatsAppTemplate.objects.filter(business=business)

    def create(self, request, *args, **kwargs):
        business = getattr(self.request.user, 'owned_businesses', None)
        business = business.first() if business else None

        if not business:
            return Response({'detail': 'No business profile attached to user.'}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Formatting Template Name for Meta requirements (lowercase, underscores only)
        raw_name = request.data.get('name', '').strip().lower()
        clean_name = re.sub(r'[^a-z0-9_]', '_', raw_name)

        if not clean_name:
            return Response({'detail': 'Template name is required.'}, status=status.HTTP_400_BAD_REQUEST)

        if WhatsAppTemplate.objects.filter(business=business, name=clean_name).exists():
            return Response({'detail': f"A template with name '{clean_name}' already exists."}, status=status.HTTP_400_BAD_REQUEST)

        template_obj = WhatsAppTemplate.objects.create(
            business=business,
            name=clean_name,
            category=request.data.get('category', WhatsAppTemplate.Category.UTILITY),
            language=request.data.get('language', WhatsAppTemplate.Language.ENGLISH_US),
            header_type=request.data.get('header_type', 'NONE'),
            header_text=request.data.get('header_text', ''),
            body_text=request.data.get('body_text', ''),
            footer_text=request.data.get('footer_text', ''),
            status=WhatsAppTemplate.Status.DRAFT
        )

        submit_now = request.data.get('submit_to_meta', True)
        if submit_now:
            connection = WhatsAppConnection.objects.filter(business=business, status=WhatsAppConnection.Status.CONNECTED).first()

            if not connection or not connection.whatsapp_business_account_id:
                return Response({
                    'detail': 'Template saved locally as draft, but no active WhatsApp WABA connection was found to submit to Meta.',
                    'template': WhatsAppTemplateSerializer(template_obj).data
                }, status=status.HTTP_201_CREATED)

            push_res = push_template_to_meta(connection, template_obj)
            if not push_res.get('success'):
                return Response({
                    'detail': f"Template created locally, but Meta submission failed: {push_res.get('error')}",
                    'template': WhatsAppTemplateSerializer(template_obj).data
                }, status=status.HTTP_201_CREATED)
            
        return Response(WhatsAppTemplateSerializer(template_obj).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='sync-status')
    def sync_template_statuses(self, request):
            """
            Polls Meta Graph API to pull updated approval states for all templates.
            """
            business = getattr(request.user, 'owned_businesses', None)
            business = business.first() if business else None

            connection = WhatsAppConnection.objects.filter(
                business=business, status=WhatsAppConnection.Status.CONNECTED
            ).first()

            if not connection or not connection.whatsapp_business_account_id:
                return Response({'detail': 'No connected WhatsApp account with valid WABA ID found.'}, status=status.HTTP_400_BAD_REQUEST)

            sync_result = fetch_remote_templates_status(connection)
            
            if sync_result.get('success'):
                return Response({
                    'detail': 'Templates synced with Meta successfully.',
                    'synced_count': sync_result.get('synced_count', 0)
                }, status=status.HTTP_200_OK)
                
            return Response({'detail': sync_result.get('error', 'Sync failed.')}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_template_campaign(request):
    """
    Dispatches an approved WhatsApp Template message to target contacts with dynamic parameters.
    Expects payload:
    {
        "template_id": "uuid",
        "contact_ids": ["uuid1", "uuid2"],
        "parameters": ["John", "ORD-1234"]  // Values mapped to {{1}}, {{2}} in order
    }
    """

    business = getattr(request.user, 'owned_businesses', None)
    business = business.first() if business else None


    if not business:
        return Response(
            {"detail": "No Business Profile Found"},
            status=status.HTTP_400_BAD_REQUEST
        ) 

    connection = WhatsAppConnection.objects.filter(business=business, status=WhatsAppConnection.Status.CONNECTED).first()

    if not connection or not connection.phone_number_id or not connection.access_token:
        return Response({'detail': 'No active WhatsApp connection configured.'}, status=status.HTTP_400_BAD_REQUEST)

    # 2. Fetch Template
    template_id = request.data.get('template_id')
    template = WhatsAppTemplate.objects.filter(id=template_id, business=business).first()

    if not template:
        return Response({'detail': 'Template not found.'}, status=status.HTTP_404_NOT_FOUND)

    if template.status != WhatsAppTemplate.Status.APPROVED:
        return Response({
            'detail': f"Cannot send campaign. Template status is '{template.status}'. Only APPROVED templates can be sent."
        }, status=status.HTTP_400_BAD_REQUEST)

    # 3. Fetch Contacts
    contact_ids = request.data.get('contact_ids', [])
    if not contact_ids:
        return Response({'detail': 'No contacts selected for campaign.'}, status=status.HTTP_400_BAD_REQUEST)

    contacts = CustomerContact.objects.filter(id__in=contact_ids, business=business, is_opted_in=True)
    if not contacts.exists():
        return Response({'detail': 'No valid opted-in contacts found from selection.'}, status=status.HTTP_400_BAD_REQUEST)

    # 4. Prepare Meta Graph API Payload Structure
    raw_params = request.data.get('parameters', [])
    body_parameters = [{"type": "text", "text": str(p)} for p in raw_params]

    components = []
    if body_parameters:
        components.append({
            "type": "body",
            "parameters": body_parameters
        })

    graph_version = getattr(settings, 'GRAPH_API_VERSION', 'v21.0')
    url = f"https://graph.facebook.com/{graph_version}/{connection.phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {connection.access_token}",
        "Content-Type": "application/json"
    }

    results = {"sent": 0, "failed": 0, "errors": []}

    # 5. Dispatch Loop
    for contact in contacts:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": str(contact.phone_number),
            "type": "template",
            "template": {
                "name": template.name,
                "language": {"code": template.language},
                "components": components
            }
        }

        try:
            res = requests.post(url, headers=headers, json=payload, timeout=15)
            res_data = res.json()

            if res.status_code in [200, 201]:
                results["sent"] += 1
                # Optional: Create MessageLog record here with wamid = res_data['messages'][0]['id']
            else:
                results["failed"] += 1
                results["errors"].append({
                    "phone": str(contact.phone_number),
                    "error": res_data.get('error', {}).get('message', 'Failed to send')
                })
        except Exception as e:
            results["failed"] += 1
            results["errors"].append({"phone": str(contact.phone_number), "error": str(e)})

    return Response({
        'detail': f"Campaign dispatch completed. Sent: {results['sent']}, Failed: {results['failed']}",
        'results': results
    }, status=status.HTTP_200_OK)