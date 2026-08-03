import requests
from django.conf import settings
from .models import WhatsAppTemplate
import re


def push_template_to_meta(connection, template_obj):
    """
    Submits a locally created template directly to Meta for review/approval.
    """
    graph_version = getattr(settings, 'GRAPH_API_VERSION', 'v21.0')
    url = f"https://graph.facebook.com/{graph_version}/{connection.whatsapp_business_account_id}/message_templates"
    
    headers = {
        "Authorization": f"Bearer {connection.access_token}",
        "Content-Type": "application/json"
    }

    # Construct Meta Components structure
    components = []

    # Optional Header
    if template_obj.header_type == 'TEXT' and template_obj.header_text:
        components.append({
            "type": "HEADER",
            "format": "TEXT",
            "text": template_obj.header_text
        })
    elif template_obj.header_type in ['IMAGE', 'DOCUMENT']:
        components.append({
            "type": "HEADER",
            "format": template_obj.header_type
        })

    # 2. Body Component + Parameter Sample Generation
    body_component = {
        "type": "BODY",
        "text": template_obj.body_text
    }

    # Extract dynamic variable tokens like {{1}}, {{2}}
    vars_found = re.findall(r'\{\{(\d+)\}\}', template_obj.body_text)
    if vars_found:
        # Generate dummy sample values required by Meta for review
        # e.g., [['Sample_1', 'Sample_2']]
        sample_values = [f"Sample_{v}" for v in sorted(set(vars_found), key=int)]
        body_component["example"] = {
            "body_text": [sample_values]
        }

    # Required Body
    components.append(body_component)

    # Optional Footer
    if template_obj.footer_text:
        components.append({
            "type": "FOOTER",
            "text": template_obj.footer_text
        })

    payload = {
        "name": template_obj.name,
        "category": template_obj.category,
        "language": template_obj.language,
        "components": components
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        res_data = response.json()

        if response.status_code in [200, 201]:
            template_obj.meta_template_id = res_data.get('id')
            template_obj.status = 'PENDING'
            template_obj.save()

            print('Template push to Meta....')
            return {"success": True, "data": res_data}
        else:
            error_msg = res_data.get('error', {}).get('message', 'Failed to create template on Meta.')
            template_obj.rejection_reason = error_msg
            template_obj.save()
            return {"success": False, "error": error_msg, "details": res_data}

    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"Network exception: {str(e)}"}

def fetch_remote_templates_status(connection):
    """
    Fetches latest approval statuses from Meta Graph API and syncs local database records.
    """
    graph_version = getattr(settings, 'GRAPH_API_VERSION', 'v21.0')
    url = f"https://graph.facebook.com/{graph_version}/{connection.whatsapp_business_account_id}/message_templates"
    
    headers = {"Authorization": f"Bearer {connection.access_token}"}

    try:
        response = requests.get(url, headers=headers, timeout=15)
        res_data = response.json()

        if response.status_code == 200:
            remote_templates = res_data.get('data', [])
            updated_count = 0

            for remote_tpl in remote_templates:
                meta_id = remote_tpl.get('id')
                name = remote_tpl.get('name')
                lang = remote_tpl.get('language')
                meta_status = remote_tpl.get('status')

                local_tpl = WhatsAppTemplate.objects.filter(
                    business=connection.business,
                    name=name,
                    language=lang
                ).first()

                if local_tpl:
                    local_tpl.meta_template_id = meta_id
                    local_tpl.status = meta_status
                    if meta_status == 'REJECTED':
                        local_tpl.rejection_reason = remote_tpl.get('rejection_reason', 'Rejected during Meta Review.')
                    local_tpl.save()
                    updated_count += 1

            return {"success": True, "synced_count": updated_count, "data": remote_templates}
        else:
            return {"success": False, "error": res_data.get('error', {}).get('message', 'Failed to fetch status.')}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}

    