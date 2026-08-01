from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required 
from django.contrib.auth import logout as django_logout
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

# REST FRAMEWORK LIBRARIES
from rest_framework.views import APIView
from rest_framework.decorators import api_view, authentication_classes, permission_classes, parser_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

# LOCAL LIBRARIES
from .models import CustomUser, Business, WhatsAppConnection, Product, ProductImage
from .serializer import CustomTokenObtainPairSerializer, RegisterSerializer, BusinessSerializer, WhatsAppConnectionSerializer, ProductSerializer, ProductImageSerializer, MetaCatalogBatchSerializer
from django.db import transaction
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
import json

# GOOGLE AUTH LIBRARIES
from dj_rest_auth.registration.views import SocialLoginView
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client

import requests
from .service import exchange_auth_code_for_token, extract_waba_id, subscribe_waba_to_webhook, link_catalog_to_waba, fetch_primary_phone_number, save_to_whatsapp_connection, create_or_get_meta_catalog, get_waba_business_id, upload_products_batch_to_meta, send_whatsApp_catalog_message
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

@login_required
def home(request):
    business = get_object_or_404(Business, owner=request.user)
    return render(request, 'home.html', {"business": business})

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
            secure=True, # Set to True if you're using HTTPS
            max_age=3600, 
            samesite=None
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
    #Logout the user from Django session
    if request.user.is_authenticated:
        django_logout(request)

    refresh_token = request.data.get('refresh_token')

    if refresh_token:
        try:
            RefreshToken(refresh_token).blacklist()
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    response = Response({"message": 'Logout Successful'}, status=status.HTTP_200_OK)
    
    response.delete_cookie('access_token')
    response.delete_cookie('refresh_token')
    response.delete_cookie('sessionid')  # Delete Django session cookie if it exists

    return response

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def create_business_profile(request):
    """
    FBV for onboarding/creating a Business Profile for the authenticated user.
    Handles form-data (for logo uploads) or standard JSON payloads.
    """

    if Business.objects.filter(owner=request.user).exists():
        return Response(
            {"detail": "You already have a business profile. Please update it instead."},
            status=status.HTTP_400_BAD_REQUEST
        )

    serializer = BusinessSerializer(data=request.data, context={'request': request})

    if serializer.is_valid():
        business = serializer.save(owner=request.user)  # Assuming a user can own only one business for now

        return Response(
            {
                "status": "success",
                "message": "Business profile created successfully.",
                "data": serializer.data
            },
            status=status.HTTP_201_CREATED
        )
    else:
        return Response(
            {
                "status": "error",
                "message": "Failed to create business profile.",
                "errors": serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sendWhatsAppMessage(request):
    recipient_phone = request.data.get("phone_number")
    image_file = request.FILES.get("image")
    message_text = request.data.get("message")

    if isinstance(recipient_phone, str):
        phone_numbers = [p.strip() for p in recipient_phone.split(',') if p.strip()]
    elif isinstance(recipient_phone, list):
        phone_numbers = [str(p).strip() for p in recipient_phone if str(p).strip()]
    else:   
        phone_numbers = []


    # 1. Validate required request payload
    if not phone_numbers or not message_text:
        return Response(
            {"detail": "All fields 'phone_number' and 'message' are required."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # 2. Retrieve the active WhatsApp connection for the authenticated user's business
    try:
        business = request.user.owned_businesses.first()  # Assuming a user can own multiple businesses, adjust as needed
        connection = WhatsAppConnection.objects.get(
            business=business,
            status=WhatsAppConnection.Status.CONNECTED
        )
    except getattr(request.user, 'owned_businesses', None) is None:
        return Response(
            {"detail": "No business profile associated with this user."},
            status=status.HTTP_400_BAD_REQUEST
        )
    except WhatsAppConnection.DoesNotExist:
        return Response(
            {"detail": "No active WhatsApp connection found for this business. Please connect your account first."},
            status=status.HTTP_404_NOT_FOUND
        )

    # 4. Dispatch Message to Meta Graph API
    graph_version = getattr(settings, 'GRAPH_API_VERSION', 'v21.0')
    auth_headers = {'Authorization': f'Bearer {connection.access_token}'}

    media_id = None

    if image_file:
        upload_url = f"https://graph.facebook.com/{graph_version}/{connection.phone_number_id}/media"
        files = {
            'file': (image_file.name, image_file.read(), image_file.content_type),
            'messaging_product': (None, 'whatsapp')
        }
        try:
            upload_res = requests.post(upload_url, headers=auth_headers, files=files, timeout=15)
            upload_data = upload_res.json()

            if upload_res.status_code == 200:
                media_id = upload_data.get('id')
            else:
                return Response({
                    "success": False,
                    "detail": "Failed to upload image file to Meta Media server.",
                    "error": upload_data.get("error", upload_data)
                }, status=upload_res.status_code)
        except requests.exceptions.RequestException as e:
            return Response({
                "success": False,
                "detail": f"Network error uploading media to Meta: {str(e)}",
                "error": str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    json_headers = {
        "Authorization": f"Bearer {connection.access_token}",
        "Content-Type": "application/json"
    }

    message_url = f"https://graph.facebook.com/{graph_version}/{connection.phone_number_id}/messages"

    results = {
        "success_count": 0,
        "failed_count": 0,
        "details": []
    }

    for recipient_phone in phone_numbers:

        if media_id:
            json_payload = {
                "messaging_product": "whatsapp",
                "to": recipient_phone,
                "type": "image",
                "image": {"id": media_id, "caption": message_text}
            }
        else:
            json_payload = {
                "messaging_product": "whatsapp",
                "to": recipient_phone,
                "type": "text",
                "text": {"body": message_text}
            }


        try:
            response = requests.post(message_url, headers=json_headers, json=json_payload, timeout=15)
            response_data = response.json()

            if response.status_code == 200:
                results['success_count'] += 1
                results['details'].append({
                    "phone_number": recipient_phone,
                    'status': 'sent',
                    "message_id": response_data.get("messages", [{}])[0].get("id")
                })
            else:
                results['failed_count'] += 1
                results['details'].append({
                    "phone": recipient_phone,
                    "status": "failed",
                    "error": response_data.get("error", response_data)
                })

        except requests.exceptions.RequestException as e:
            results["failed_count"] += 1
            results["details"].append({
                "phone": recipient_phone,
                "status": "failed",
                "error": f"Network error: {str(e)}"
            })

    return Response({
        "success": True,
        "total_recipients": len(phone_numbers),
        "summary": results
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
def exchange_code_for_access_token(request):
    code = request.data.get('code') or request.data.get('auth_code')
    client_waba_id = request.data.get('waba_id')
    redirect_uri = request.data.get('redirect_uri', '')

    if not code:
        return Response({'detail': 'Authorization code is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # 1. Exchange OAuth Code
        user_access_token = exchange_auth_code_for_token(code, redirect_uri)

        # 2. Extract or Validate WABA ID
        waba_id = extract_waba_id(user_access_token)

        # 3. Subscribe WABA to Webhooks
        subscribe_waba_to_webhook(waba_id, user_access_token)

        access_token = settings.META_SYSTEM_USER_TOKEN

        # 4. Determine & Link Catalog
        business = get_object_or_404(Business, owner=request.user)
        waba_business_id = get_waba_business_id(waba_id, access_token)
        catalog_id = create_or_get_meta_catalog(
            business_name=business.name, 
            access_token=user_access_token,
        )

        # Use system user token or user access token to link catalog to WABA
        catalog_token = access_token 
        link_catalog_to_waba(waba_id, catalog_id, catalog_token)

        # 5. Fetch Primary Phone Details
        primary_phone = fetch_primary_phone_number(waba_id, user_access_token)

        # 6. Save Connection to DB (including catalog_id)
        connection = save_to_whatsapp_connection(
            business=business,
            waba_id=waba_id,
            phone_info=primary_phone,
            access_token=user_access_token,
            catalog_id=catalog_id 
        )

        #print(f"✅ Saved WhatsApp Connection for {business} with Catalog ID {catalog_id}: {connection}")

        return Response({
                'success': True,
                'message': 'WhatsApp account connected successfully.',
                'data': {
                    'connection_id': str(connection.id),
                    'waba_id': connection.whatsapp_business_account_id,
                    'phone_number_id': connection.phone_number_id,
                    'catalog_id': connection.catalog_id,  # <-- RETURNED IN RESPONSE
                    'display_phone_number': connection.display_phone_number,
                    'status': connection.status,
                    'connected_at': connection.connected_at
                }
            }, status=status.HTTP_200_OK)

    except ValueError as val_err:
        return Response({'success': False, 'error': str(val_err)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'success': False, 'error': f"Internal server error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def whatsApp_webhook(request):
    if request.method == 'GET':
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')

        if mode and token:
            if mode == 'subscribe':
                connection_exists = WhatsAppConnection.objects.filter(verify_token=token).exists()

                global_token = getattr(settings, 'WHATSAPP_VERIFY_TOKEN', None)

                if connection_exists or (global_token and token == global_token):
                    print("✅ Webhook Verified Successfully!")
                    return HttpResponse(challenge, status=200)

        print("❌ Webhook Verification Failed: Token mismatch.")
        return HttpResponse('Verification token mismatch', status=403)

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            print("📩 Incoming Webhook Event:", json.dumps(data, indent=2))

            entries = data.get('entry', [])
            for entry in entries:
                changes = entry.get('changes', [])
                for change in changes:
                    value = change.get('value', {})
                    statuses = value.get('statuses', [])

                    for status_item in statuses:
                        wamid = status_item.get('id')             # e.g., "wamid.HBgM..."
                        msg_status = status_item.get('status')   # sent, delivered, read, failed
                        recipient_id = status_item.get('recipient_id')
                        timestamp = status_item.get('timestamp')

                        print(f"📊 Status Update -> Message {wamid} to {recipient_id} is now: {msg_status.upper()}")

                        # Check for delivery/sent failures
                        if msg_status == 'failed':
                            errors = status_item.get('errors', [])
                            print(f"⚠️ Message Failure Details: {errors}")

                        # TODO: Update message status in your database model here
                        # MessageLog.objects.filter(wamid=wamid).update(status=msg_status)

                    messages = value.get('messages', [])
                    for message in messages:
                        from_number = message.get('from')
                        msg_type = message.get('type')

                        if msg_type == 'text':
                            text_body = message.get('text', {}).get('body')
                            print(f"💬 New Incoming Message from {from_number}: '{text_body}'")

            # Always return a 200 OK quickly so Meta doesn't retry delivery
            return HttpResponse('EVENT_RECEIVED', status=200)

        except Exception as e:
            print("❌ Webhook Error:", str(e))
            return HttpResponse('EVENT_RECEIVED', status=200) 

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def product_list_or_create(request):
    """
    GET: List all products belonging to the authenticated merchant.
    POST: Create a product AND save gallery images in a single request.
    """

    if not hasattr(request.user, 'owned_businesses'):
        return Response({
            "status": "error",
            "detail": "No business profile associated with this account."
        }, status=status.HTTP_400_BAD_REQUEST)

    business = request.user.owned_businesses.first()

    if request.method == "GET":
        products = Product.objects.filter(business=business).prefetch_related('additional_images')
        serializer = ProductSerializer(products, maney=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method == 'POST':
        serializer = ProductSerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            with transaction.atomic():

                product = serializer.save(business=business)

                additional_files = request.FILES.getlist('additional_images')
                for image_file in additional_files:
                    ProductImage.objects.create(product=product, image=image_file)

                additional_urls = request.data.get('additional_image_urls', [])
                if isinstance(additional_urls, list):
                    for url in additional_urls:
                        ProductImage.objects.create(product=product, image_url_override=url)

            response_serializer = ProductSerializer(product, context={'request': request})
            return Response(
                response_serializer.data, status=status.HTTP_201_CREATED
            ) 

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def product_detail_view(request, pk):
    """
    GET: Retrieve single product.
    PUT/PATCH: Update product details AND handle gallery image updates/removals.
    DELETE: Delete product and associated gallery images.
    """
    if not hasattr(request.user, 'owned_businesses'):
        return Response(
            {"status": "error", "detail": "No business profile associated with this account."},
            status=status.HTTP_400_BAD_REQUEST
        )

    product = get_object_or_404(Product, pk=pk, business=request.user.owned_businesses)

    if request.method == 'GET':
        serializer = ProductSerializer(product, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method in ['PUT', 'PATCH']:
        partial = (request.method == 'PATCH')
        serializer = ProductSerializer(product, data=request.data, partial=partial, context={'request': request})
        
        if serializer.is_valid():
            with transaction.atomic():
                # 1. Update product base fields
                product = serializer.save()

                # 2. Append new gallery files if uploaded during update
                new_files = request.FILES.getlist('additional_images')
                for file in new_files:
                    ProductImage.objects.create(product=product, image=file)

                # 3. Optional: Delete specific image IDs if client requested deletion
                images_to_delete = request.data.get('delete_image_ids', [])
                if isinstance(images_to_delete, list) and images_to_delete:
                    ProductImage.objects.filter(id__in=images_to_delete, product=product).delete()

            response_serializer = ProductSerializer(product, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        product.delete()
        return Response(
            {"status": "success", "message": "Product and associated images deleted successfully."},
            status=status.HTTP_204_NO_CONTENT
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_business_products_to_catalog(request):
    """
    Fetches active products for the merchant and uploads/updates 
    them in bulk to Meta Commerce Catalog via Graph API.
    """
    if not hasattr(request.user, 'owned_businesses'):
        return Response({
            "status": "error",
            "detail": "No business profile found for this user account."
        }, status=status.HTTP_400_BAD_REQUEST)

    business = request.user.owned_businesses.first()
    whatsapp_conn = getattr(business, 'whatsapp_connection', None)

    # Validate WhatsApp connection & Catalog ID presence
    if not whatsapp_conn or not whatsapp_conn.catalog_id:
        return Response({
            "status": "error",
            "detail": "WhatsApp Connection or Catalog ID is not configured for this business."
        }, status=status.HTTP_400_BAD_REQUEST)

    # Optional filtering by specific product IDs
    product_ids = request.data.get('product_ids', [])
    products_qs = Product.objects.filter(business=business)

    if product_ids:
        products_qs = products_qs.filter(id__in=product_ids)

    if not products_qs.exists():
        return Response({
            "status": "error",
            "detail": "No products found to synchronize."
        }, status=status.HTTP_400_BAD_REQUEST)

    # 1. Format products into Meta Batch API schema
    batch_serializer = MetaCatalogBatchSerializer(products_qs, many=True, context={"request": request})
    batch_payload_requests = batch_serializer.data

    # 2. Trigger Batch Request to Meta API
    result = upload_products_batch_to_meta(
        catalog_id=whatsapp_conn.catalog_id,
        access_token=whatsapp_conn.access_token,
        products_data=batch_payload_requests
    )

    # 3. Update Sync Timestamp & Status on DB Records
    if result.get("success"):
        products_qs.update(
            is_synced_to_meta=True, 
            last_synced_at=timezone.now()
        )

        return Response({
            "status": "success",
            "message": f"Successfully synced {len(batch_payload_requests)} products to Meta Catalog!",
            "catalog_id": whatsapp_conn.catalog_id,
            "meta_response": result.get("data")
        }, status=status.HTTP_200_OK)
    else:
        return Response({
            "status": "error",
            "detail": "Failed to sync catalog batch with Meta.",
            "error": result.get("error")
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_catalog(request):
    """
    POST payload: {
        "recipient_phones": ["233595467122", "233240000000"],  # OR single string "233595467122, 233240000000"
        "product_ids": ["uuid1", "uuid2"]                      # Optional
    }
    """

    user = request.user

    if hasattr(user, "owned_businesses"):
        business = user.owned_businesses.first()
    else:
        business = None

    if not business and business == None:
        return Response(
            {'detail': 'Business Portfolio not available for this account.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        connection = WhatsAppConnection.objects.get(business=business, status=WhatsAppConnection.Status.CONNECTED)
    except WhatsAppConnection.DoesNotExist:
        return Response(
            {'detail': 'Connected WhatsApp Connection does not exist!'},
            status=status.HTTP_400_BAD_REQUEST
        )

    raw_phones = request.data.get('recipient_phones')
    if not raw_phones:
        return Response(
            {'detail': 'At least one recipient phone number is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if isinstance(raw_phones, str):
        recipient_phones = [p.strip() for p in raw_phones.split(',') if p.strip()]

    elif isinstance(raw_phones, list):
        recipient_phones = raw_phones
    else:
        recipient_phones = [str(raw_phones)]

    selected_products_id = request.data.get('product_ids', [])
    product_qs = Product.objects.filter(business=business, is_synced_to_meta=True)

    if selected_products_id:
        product_qs = Product.objects.filter(id__in=selected_products_id)

    if not product_qs.exists():
        return Response(
            {'detail': 'No synced products found in catalog to send.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Extract Meta content_ids (e.g. PROD-D57FF5)
    product_retailer_ids = list(product_qs.values_list('content_id', flat=True))
    
    # 4. Trigger Catalog Helper
    catalog_id = connection.catalog_id

    result = send_whatsApp_catalog_message(
        phone_number_id=connection.phone_number_id,
        access_token=connection.access_token,
        recipient_phones=recipient_phones,
        catalog_id=catalog_id,
        product_retailer_ids=product_retailer_ids,
        header_text=f"{business.name} Collection",
        body_text="Explore our catalog below and tap to order directly!"
    )

    if result["success"]:
        return Response({
            'status': 'success',
            'summary': {
                'total_sent': result["total_sent"],
                'total_successful': result["total_successful"],
                'total_failed': result["total_failed"]
            },
            'results': result["recipient_results"]
        }, status=status.HTTP_200_OK)
    else:
        return Response({
            'status': 'error',
            'detail': 'Failed to send WhatsApp product list to any recipient.',
            'summary': {
                'total_sent': result["total_sent"],
                'total_successful': result["total_successful"],
                'total_failed': result["total_failed"]
            },
            'results': result["recipient_results"]
        }, status=status.HTTP_400_BAD_REQUEST)