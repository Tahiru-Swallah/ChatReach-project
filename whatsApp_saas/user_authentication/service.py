import requests
from django.conf import settings
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework import status
from .models import WhatsAppConnection

def exchange_auth_code_for_token(code: str, redirect_uri: str = '') -> str:
    """Exchanges Meta OAuth authorization code for a User Access Token."""

    token_exchange_url = f"https://graph.facebook.com/{settings.GRAPH_API_VERSION}/oauth/access_token" 

    # DO NOT include 'redirect_uri' or 'grant_type' here when using FB.login()
    params = {
        'client_id': settings.META_APP_ID,
        'client_secret': settings.META_APP_SECRET,
        'redirect_uri': redirect_uri,
        'code': code
    }

    token_response = requests.get(token_exchange_url, params=params)
    token_data = token_response.json()

    if 'error' in token_data and token_data['error'].get('code') == 100:

        print("⚠️ Initial exchange failed, retrying without redirect_uri parameter...")

        params.pop('redirect_uri', None)

        token_response = requests.get(token_exchange_url, params=params)
        token_data = token_response.json()

    if 'error' in token_data:
        print("❌ Meta Token Exchange Error:", token_data)
        raise ValueError(f"Meta Token Exchange Error: {token_data['error']}")
    
    user_access_token = token_data.get('access_token')

    return user_access_token

def extract_waba_id(access_token: str):
    """Inspects the token debug endpoint to extract the WABA ID if missing."""

    debug_url = f"https://graph.facebook.com/{settings.GRAPH_API_VERSION}/debug_token"
    debug_params = {
        'input_token': access_token,
        'access_token': f"{settings.META_APP_ID}|{settings.META_APP_SECRET}"
    }

    try:

        debug_response = requests.get(debug_url, params=debug_params)
        res_json = debug_response.json()

        # Meta returns token details nested inside 'data'
        debug_data = res_json.get('data', {})

        for scope in debug_data.get('granular_scopes', []):
            if scope.get('scope') == 'whatsapp_business_management':
                target_ids = scope.get('target_ids', [])
                if target_ids:
                    waba_id = target_ids[0]
                    print(f"🔑 Successfully extracted WABA ID from token permissions: {waba_id}")
                    return waba_id

    except requests.exceptions.RequestException as err:
        print(f"❌ Network error inspecting token: {str(err)}")

    raise ValueError('Could not extract WABA ID from token permissions.')

def subscribe_waba_to_webhook(waba_id: str, access_token: str) -> bool:
    """Subscribes the WABA to receive webhooks from your Meta App."""

    subscribe_url = f"https://graph.facebook.com/{settings.GRAPH_API_VERSION}/{waba_id}/subscribed_apps"
    headers = {"Authorization": f"Bearer {access_token}"}

    subscribe_resp = requests.post(subscribe_url, headers=headers)
    subscribe_data = subscribe_resp.json()

    print(f"🔔 Subscribed App to WABA Response: {subscribe_data}")
    return subscribe_data.get('success', False)

def link_catalog_to_waba(waba_id: str, catalog_id: str, access_token: str) -> bool:
    """
    Associates a Meta Commerce Catalog with the WABA.
    Gracefully handles cases where the catalog is already linked or token lacks catalog_management scope.
    """
    version = getattr(settings, 'GRAPH_API_VERSION', 'v21.0')
    headers = {"Authorization": f"Bearer {access_token}"}

    # 1. First, check if the catalog is ALREADY connected to the WABA
    get_catalogs_url = f"https://graph.facebook.com/{version}/{waba_id}/product_catalogs"
    
    try:
        get_resp = requests.get(get_catalogs_url, headers=headers)
        if get_resp.status_code == 200:
            connected_catalogs = get_resp.json().get('data', [])
            connected_ids = [cat.get('id') for cat in connected_catalogs]
            
            if catalog_id in connected_ids:
                print(f"ℹ️ Catalog {catalog_id} is ALREADY linked to WABA {waba_id}. Skipping POST request.")
                return True
    except Exception as check_err:
        print(f"⚠️ Could not verify existing catalog links: {str(check_err)}")

    # 2. If not linked, execute the POST request using System User Token if available
    # (Fallback to user access_token)
    catalog_token = getattr(settings, 'META_SYSTEM_USER_TOKEN', access_token)
    link_headers = {"Authorization": f"Bearer {catalog_token}"}
    
    payload = {"catalog_id": catalog_id}

    try:
        catalog_resp = requests.post(get_catalogs_url, headers=link_headers, data=payload)
        catalog_data = catalog_resp.json()

        if catalog_resp.status_code == 200 and catalog_data.get("success"):
            print(f"🛍️ Catalog {catalog_id} successfully linked to WABA {waba_id}!")
            return True
        elif 'error' in catalog_data and catalog_data['error'].get('code') == 100:
            # Code 100 / Subcode 33 usually means already linked or scope warning; safe to continue
            print(f"ℹ️ Catalog {catalog_id} link acknowledged by Meta (Code 100). Continuing onboarding.")
            return True
        else:
            print(f"⚠️ Could not link catalog to WABA: {catalog_data}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Network error while linking catalog: {str(e)}")
        return False

def fetch_primary_phone_number(access_token: str, waba_id: str) -> dict:
    """
    Retrieves connected phone numbers for the WABA.
    Returns primary phone data if found, or fallback defaults if the array is empty.
    """
    version = getattr(settings, 'GRAPH_API_VERSION', 'v21.0')
    phone_url = f"https://graph.facebook.com/{version}/{waba_id}/phone_numbers"
    headers = {"Authorization": f"Bearer {access_token}"}

    # 1. Try querying phone numbers via User Access Token
    try:
        response = requests.get(phone_url, headers=headers, timeout=10)
        phone_data = response.json()
        phone_numbers = phone_data.get('data', [])

        if phone_numbers:
            print(f"📱 Found Phone Number ID: {phone_numbers[0].get('id')} via User Token")
            return phone_numbers[0]
            
    except requests.exceptions.RequestException as err:
        print(f"⚠️ Primary phone lookup failed with user token: {str(err)}")

    # 2. Try App Access Token (Required for Meta Test Numbers)
    print("🔄 User token returned no numbers. Retrying with App Access Token...")
    app_token = f"{settings.META_APP_ID}|{settings.META_APP_SECRET}"
    app_headers = {"Authorization": f"Bearer {app_token}"}

    try:
        app_resp = requests.get(phone_url, headers=app_headers, timeout=10)
        app_data = app_resp.json()
        phone_numbers = app_data.get('data', [])

        if phone_numbers:
            print(f"📱 Found Phone Number ID: {phone_numbers[0].get('id')} via App Access Token")
            return phone_numbers[0]
            
    except Exception as fallback_err:
        print(f"⚠️ Fallback phone lookup failed: {str(fallback_err)}")

    # 3. Fallback for Local Dev / Test Accounts
    default_phone_id = getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', None)
    default_display_num = getattr(settings, 'WHATSAPP_DISPLAY_PHONE_NUMBER', 'Pending Setup')

    if default_phone_id:
        print(f"ℹ️ Using fallback development Phone ID: {default_phone_id}")
        return {
            'id': default_phone_id,
            'display_phone_number': default_display_num
        }

    # 4. Safe Return instead of raising a breaking ValueError
    print(f"⚠️ WABA {waba_id} has no registered phone numbers attached yet.")
    return {
        'id': 'PENDING',
        'display_phone_number': 'Pending Phone Registration'
    }


def save_to_whatsapp_connection(business, waba_id: str, phone_info: dict, access_token: str, catalog_id: str) -> WhatsAppConnection:
    """
    Creates or updates the WhatsAppConnection record in the database.
    Preserves existing phone details if Meta API returns empty phone numbers during re-authentication.
    """
    # 1. Fetch existing connection if it exists
    existing_connection = WhatsAppConnection.objects.filter(business=business).first()

    # 2. Extract phone info or fallback to existing database values
    phone_number_id = phone_info.get('id') if phone_info else None
    display_phone_number = phone_info.get('display_phone_number') if phone_info else None

    # If API returned None or 'PENDING', keep what's already saved in DB!
    if not phone_number_id or phone_number_id == 'PENDING':
        if existing_connection and existing_connection.phone_number_id:
            phone_number_id = existing_connection.phone_number_id
            display_phone_number = existing_connection.display_phone_number
        else:
            # Absolute fallback for brand new setups where API returned empty
            phone_number_id = getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', 'PENDING')
            display_phone_number = getattr(settings, 'WHATSAPP_DISPLAY_PHONE_NUMBER', 'Pending')

    # 3. Update or create record without losing phone_number_id
    connection, _ = WhatsAppConnection.objects.update_or_create(
        business=business,
        defaults={
            'whatsapp_business_account_id': waba_id,
            'phone_number_id': phone_number_id,
            'display_phone_number': display_phone_number,
            'access_token': access_token,
            'catalog_id': catalog_id,
            'status': WhatsAppConnection.Status.CONNECTED,
            'connected_at': timezone.now()
        }
    )
    return connection

def create_or_get_meta_catalog(business_name: str, access_token: str, business_id: str = None) -> str:
    """
    Retrieves an existing catalog or programmatically creates a new product catalog 
    for the business using Meta Graph API.
    
    Falls back to `WINIMARKET_CATALOG_ID` setting if catalog creation fails or is unconfigured.
    """
    default_catalog_id = getattr(settings, 'WINIMARKET_CATALOG_ID', '28733519179570722')
    version = getattr(settings, 'GRAPH_API_VERSION', 'v21.0')
    headers = {'Authorization': f'Bearer {access_token}'}

    # ------------------------------------------------------------------
    # STEP 1: Get Business Portfolio ID if not explicitly passed
    # ------------------------------------------------------------------
    if not business_id:
        try:
            me_biz_url = f"https://graph.facebook.com/{version}/me/businesses"
            response = requests.get(me_biz_url, headers=headers, timeout=10)
            biz_data = response.json()
            
            businesses = biz_data.get('data', [])
            if businesses:
                business_id = businesses[0].get('id')
        except Exception as e:
            print(f"⚠️ Could not fetch Business Portfolio ID: {str(e)}")

    if not business_id:
        print("⚠️ No Business ID available. Using default fallback catalog ID.")
        return default_catalog_id

    # ------------------------------------------------------------------
    # STEP 2: Check for existing catalogs under this Business Portfolio
    # ------------------------------------------------------------------
    try:
        get_catalogs_url = f"https://graph.facebook.com/{version}/{business_id}/owned_product_catalogs"
        get_resp = requests.get(get_catalogs_url, headers=headers, timeout=10)
        existing_catalogs = get_resp.json().get('data', [])

        if existing_catalogs:
            catalog_id = existing_catalogs[0].get('id')
            print(f"📦 Found existing Meta Catalog '{existing_catalogs[0].get('name')}' (ID: {catalog_id})")
            return catalog_id
    except Exception as e:
        print(f"⚠️ Error checking existing catalogs: {str(e)}")

    # ------------------------------------------------------------------
    # STEP 3: Programmatically create a new Catalog via Graph API
    # ------------------------------------------------------------------
    try:
        create_catalog_url = f"https://graph.facebook.com/{version}/{business_id}/owned_product_catalogs"
        payload = {
            'name': f"{business_name} Catalog",
            'vertical': 'commerce'  # Vertical type for retail/e-commerce goods
        }

        create_resp = requests.post(create_catalog_url, headers=headers, json=payload, timeout=10)
        create_data = create_resp.json()

        if create_resp.status_code == 200 and 'id' in create_data:
            new_catalog_id = create_data['id']
            print(f"✨ Successfully created new Meta Catalog ID: {new_catalog_id}")
            return new_catalog_id
        else:
            print(f"❌ Failed to create catalog via Graph API: {create_data}")

    except requests.exceptions.RequestException as req_err:
        print(f"❌ Network error while creating catalog: {str(req_err)}")

    # ------------------------------------------------------------------
    # STEP 4: Fallback
    # ------------------------------------------------------------------
    print(f"🔄 Returning default catalog fallback ID: {default_catalog_id}")
    return default_catalog_id

def get_waba_business_id(waba_id: str, access_token: str) -> str:
    """
    Retrieves the Meta Business Portfolio ID owning the specified WABA ID.
    
    Args:
        waba_id (str): The WhatsApp Business Account ID.
        access_token (str): User or System User access token.
        
    Returns:
        str: The Business Portfolio ID if found, otherwise None.
    """

    waba_url = f"https://graph.facebook.com/{settings.GRAPH_API_VERSION}/{waba_id}"
    headers = {"Authorization": f"Bearer {access_token}"}

    # Query WABA fields including owner_business_info
    params = {
        'fields': 'id,name,owner_business_info'
    }

    try:
        response = requests.get(waba_url, headers=headers, params=params)
        waba_data = response.json()

        if response.status_code == 200:
            owner_info = waba_data.get("owner_business_info", {})

            business_id = owner_info.get('id')

            if business_id:
                print(f"💼 Retrieved Business Portfolio ID: {business_id} for WABA: {waba_id}")
                return business_id
            
            print(f"⚠️ WABA {waba_id} returned response, but 'owner_business_info' was empty.")

        else:
            print(f"❌ Error fetching WABA details ({response.status_code}): {waba_data}")

    except requests.exceptions.RequestException as req_err:
        print(f"❌ Network exception while retrieving WABA Business ID: {str(req_err)}")

    # Fallback Option: Query /me/businesses if owner_business_info was unavailable
    try:
        fallback_url = f"https://graph.facebook.com/{settings.GRAPH_API_VERSION}/me/businesses"
        fb_resp = requests.get(fallback_url, headers=headers, timeout=10)
        fb_data = fb_resp.json()
        
        businesses = fb_data.get('data', [])
        if businesses:
            fallback_biz_id = businesses[0].get('id')
            print(f"🔄 Fallback retrieved Business Portfolio ID: {fallback_biz_id}")
            return fallback_biz_id
    except Exception as e:
        print(f"⚠️ Fallback search failed: {str(e)}")

    return None

# ==============================================================================
# HELPER: META CATALOG BATCH UPLOAD FUNCTION
# ==============================================================================

def generate_whatsapp_product_link(phone_number, product_name):
    """Generates a wa.me link for buyers to inquire about the product."""
    import urllib.parse
    clean_phone = phone_number.replace("+", "").replace(" ", "")
    encoded_msg = urllib.parse.quote(f"Hi! I'm interested in buying '{product_name}'. Is it available?")
    return f"https://wa.me/{clean_phone}?text={encoded_msg}"

def upload_products_batch_to_meta(catalog_id: str, access_token: str, products_data: list) -> dict:
    """
    Submits a batch upload request to Meta Commerce Manager Catalog.
    
    Args:
        catalog_id (str): Meta Commerce Catalog ID.
        access_token (str): System User or User Access Token with catalog_management scopes.
        products_data (list): List of dicts containing product details.
        
    Returns:
        dict: Response from Meta's /{catalog_id}/batch endpoint.
    """
    version = getattr(settings, 'GRAPH_API_VERSION', 'v21.0')
    batch_url = f"https://graph.facebook.com/{version}/{catalog_id}/batch"

    requests_payload = []
    for item in products_data:
        # Check if the item is already structured by MetaCatalogBatchSerializer
        if "retailer_id" in item and "data" in item:
            requests_payload.append(item)
        else:
            # Fallback for raw model dicts or unformatted inputs
            payload_data = item.get("data", item)
            price_val = payload_data.get("price", 0)

            if isinstance(price_val, (float, str)):
                price_minor_units = int(float(price_val) * 100)
            else:
                price_minor_units = price_val

            retailer_id = item.get("retailer_id") or item.get("content_id")
            
            # Use 'get_public_image_url' or 'image' if 'image_url' is missing
            image_url = (
                item.get("image_url") 
                or item.get("get_public_image_url") 
                or item.get("image")
            )

            requests_payload.append({
                "method": item.get("method", "UPDATE"),
                "retailer_id": str(retailer_id),
                "data": {
                    "name": payload_data.get("name"),
                    "description": payload_data.get("description") or payload_data.get("name"),
                    "brand": payload_data.get("brand") or payload_data.get("seller"),
                    "price": price_minor_units,
                    "currency": payload_data.get("currency", "GHS"),
                    "availability": payload_data.get("availability", "in stock"),
                    "condition": payload_data.get("condition", "new"),
                    "image_url": image_url,
                    "additional_image_urls": payload_data.get("additional_image_urls", []),
                    "url": payload_data.get("url"),
                }
            })
    payload = {
        "requests": requests_payload
    }

    # Use System User Token if provided/configured, fallback to passed access_token
    token = getattr(settings, 'META_SYSTEM_USER_TOKEN', access_token)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(batch_url, headers=headers, json=payload, timeout=20)
        res_data = response.json()

        if response.status_code == 200:
            print(f"✅ Successfully submitted batch of {len(products_data)} products to catalog {catalog_id}")
            return {"success": True, "data": res_data}
        else:
            print(f"❌ Meta Batch Upload Failed: {res_data}")
            return {"success": False, "error": res_data}

    except requests.exceptions.RequestException as err:
        print(f"❌ Network error uploading products batch: {str(err)}")
        return {"success": False, "error": str(err)}

def send_whatsApp_catalog_message(phone_number_id, access_token, recipient_phones, catalog_id, product_retailer_ids, header_text="Our Collection", body_text="Explore our catalog below and tap to order directly!", footer_text="Powered by Chatreach", section_title="Featured Items"):

    """
    Sends a WhatsApp Interactive Multi-Product Message (Product List).
    WhatsApp Limits: Max 30 total items per message, max 10 items per section.
    """

    url = f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    print(f"Product IDS: {product_retailer_ids}")
    # Format product retailer IDs into WhatsApp schema
    # Cap at 30 items max per WhatsApp Cloud API specification
    capped_ids = product_retailer_ids[:30]

    print(f"CAPPED_IDS: {capped_ids}")

    # Group into sections (up to 10 products per section)
    sections = []
    chunk_size = 10

    for i in range(0, len(capped_ids), chunk_size):
        chunk = capped_ids[i:i + chunk_size]
        print(f"Chunks: {chunk}")
        sections.append(
            {
                "title": f"{section_title} ({len(sections) + 1})" if len(capped_ids) > 10 else section_title,
                "product_items": [{"product_retailer_id": str(pid)} for pid in chunk]
            }
        )

    print(f"SECTIONS: {sections}")

    if isinstance(recipient_phones, str):
        recipient_phone = [recipient_phones]

    results = []
    total_successful = 0
    total_failed = 0

    for phone in recipient_phones:
        clean_phone = "".join(filter(str.isdigit, (phone)))
        print(clean_phone)

        if not clean_phone:
            results.append({
                "recipient": phone,
                "status": "failed",
                "error": "Invalid or empty phone number format."
            })
            total_failed += 1
            continue

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_phone,
            "type": "interactive",
            "interactive": {
                "type": "product_list",
                "header": {
                    "type": "text",
                    "text": header_text
                },
                "body": {
                    "text": body_text
                },
                "footer": {
                    "text": footer_text
                },
                "action": {
                    "catalog_id": str(catalog_id),
                    "sections": sections
                }
            }
        }

        """ payload2 = {'messaging_product': 'whatsapp', 'recipient_type': 'individual', 'to': '233595467122', 'type': 'interactive', 'interactive': {'type': 'product_list', 'header': {'type': 'text', 'text': 'Tahiru Swallah Collection'}, 'body': {'text': 'Explore our catalog below and tap to order directly!'}, 'footer': {'text': 'Powered by Chatreach'}, 'action': {'catalog_id': '28733519179570722', 'sections': [{'title': 'Featured Items', 'product_items': [{'product_retailer_id': 'PROD-CE32C2'}]}]}}} """

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            res_data = response.json()

            if response.status_code == 200:
                message_id = res_data.get("message", [{}])[0].get('id')
                results.append({
                    "recipient": clean_phone,
                    "status": "success",
                    "message_id": message_id,
                    "data": res_data
                })
                total_successful += 1
            else:
                results.append({
                    "recipient": clean_phone,
                    "status": "failed",
                    "error": res_data
                })
                total_failed += 1

        except requests.exceptions.RequestException as e:
            results.append({
                "recipient": clean_phone,
                "status": "failed",
                "error": f"Network communication error: {str(e)}"
            })
            total_failed += 1
        
    return {
        "success": total_successful > 0,
        "total_sent": len(recipient_phones),
        "total_successful": total_successful,
        "total_failed": total_failed,
        "recipient_results": results
    }

def send_whatsapp_direct_message(phone_number_id, access_token, recipient_phones, message_text, image_file=None):
    """
    Modular helper to send text or image/caption messages to Meta Graph API.
    Handles media upload first if an image file is attached.
    """
    graph_version = getattr(settings, 'GRAPH_API_VERSION', 'v21.0')
    auth_headers = {'Authorization': f'Bearer {access_token}'}
    media_id = None

    # 1. Handle Optional Image Upload to Meta Media Endpoint
    if image_file:
        upload_url = f"https://graph.facebook.com/{graph_version}/{phone_number_id}/media"
        # Reset file pointer if read previously
        image_file.seek(0)
        files = {
            'file': (image_file.name, image_file.read(), image_file.content_type),
            'messaging_product': (None, 'whatsapp')
        }

        try:
            upload_res = requests.post(upload_url, headers=auth_headers, files=files, timeout=20)
            upload_data = upload_res.json()

            if upload_res.status_code == 200:
                media_id = upload_data.get('id')
            else:
                return {
                    "success": False,
                    "error": "Failed to upload image file to Meta Media server.",
                    "details": upload_data.get("error", upload_data)
                }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"Network error during media upload: {str(e)}"
            }

    # 2. Dispatch Messages to Recipients
    message_url = f"https://graph.facebook.com/{graph_version}/{phone_number_id}/messages"
    json_headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    results = {
        "total_sent": len(recipient_phones),
        "total_successful": 0,
        "total_failed": 0,
        "recipient_results": []
    }

    for phone in recipient_phones:
        clean_phone = phone.lstrip('+')

        if media_id:
            json_payload = {
                "messaging_product": "whatsapp",
                "to": clean_phone,
                "type": "image",
                "image": {"id": media_id, "caption": message_text}
            }
        else:
            json_payload = {
                "messaging_product": "whatsapp",
                "to": clean_phone,
                "type": "text",
                "text": {"body": message_text}
            }

        try:
            response = requests.post(message_url, headers=json_headers, json=json_payload, timeout=15)
            response_data = response.json()

            if response.status_code == 200:
                results['total_successful'] += 1
                msg_id = response_data.get("messages", [{}])[0].get("id")
                results['recipient_results'].append({
                    "phone_number": clean_phone,
                    "status": "sent",
                    "message_id": msg_id
                })
            else:
                results['total_failed'] += 1
                results['recipient_results'].append({
                    "phone_number": clean_phone,
                    "status": "failed",
                    "error": response_data.get("error", response_data)
                })

        except requests.exceptions.RequestException as e:
            results["total_failed"] += 1
            results["recipient_results"].append({
                "phone_number": clean_phone,
                "status": "failed",
                "error": f"Network error: {str(e)}"
            })
            
    results["success"] = results["total_successful"] > 0
    return results