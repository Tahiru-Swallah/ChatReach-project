from django.conf import settings
import requests

def initialize_payment(email, amount, callback_url):
    url = "https://api.paystack.co/transaction/initialize"
    headers = {
        'Authorization': f'Bearer {settings.PAYSTACK_TESTED_SECRET_API_KEY}',
        'Content-Type': 'application/json'
    }
    data = {
        'email': email,
        'amount': int(amount) * 100,
        'callback_url': callback_url,
        'channels': ['mobile_money', 'card'],
        'currency': "GHS"
    }

    response = requests.post(url, headers=headers, json=data)
    return response.json()

def verify_payment(reference):
    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {
        'Authorization': f'Bearer {settings.PAYSTACK_TESTED_SECRET_API_KEY}'
    }
    response = requests.get(url, headers=headers)
    return response.json()