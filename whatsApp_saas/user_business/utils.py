import requests
from django.conf import settings

INFOBIP_API_KEY = settings.INFOBIP_API_KEY
INFOBIP_BASE_URL = settings.INFOBIP_BASE_URL
INFOBIP_SENDER = settings.INFOBIP_SENDER # Infobip test sender

def send_whatsapp_message(phone_number, message_template):
    url = f'{INFOBIP_BASE_URL}/whatsapp/1/message/text'

    headers = {
        "Authorization": f"App {INFOBIP_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    data = {
        "messages": [
            {
                "from": str(settings.INFOBIP_SENDER),  # your approved Infobip sender number
                "to": phone_number,
                "content": {
                    "templateName": message_template.template_name,
                    "templateData": {
                        "body": {
                            "placeholders": message_template.placeholders or []
                        }
                    },
                    "language": message_template.language
                }
            }
        ]
    }

    response = requests.post(url, json=data, headers=headers)

    if response.status_code >= 400:
        raise Exception(f"Infobip Error: {response.status_code} - {response.text}")

    return response.json()