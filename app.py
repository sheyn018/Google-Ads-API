from flask import Flask, request, jsonify
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from datetime import datetime, timedelta
from typing import List, Dict
from google.auth.exceptions import RefreshError
from google.api_core import exceptions as google_exceptions

app = Flask(__name__)

def get_last_month_date_range():
    today = datetime.today()
    first_day = datetime(today.year, today.month, 1) - timedelta(days=1)
    last_month_first_day = first_day.replace(day=1)
    last_month_last_day = first_day
    
    return (
        last_month_first_day.strftime('%Y-%m-%d'),
        last_month_last_day.strftime('%Y-%m-%d')
    )

def get_campaign_billing(client, customer_id: str, start_date: str, end_date: str) -> List[Dict]:
    ga_service = client.get_service("GoogleAdsService")
    
    query = """
        SELECT
            campaign.id,
            campaign.name,
            metrics.cost_micros,
            campaign.status
        FROM campaign
        WHERE 
            segments.date BETWEEN '{start_date}' AND '{end_date}'
        """.format(start_date=start_date, end_date=end_date)
    
    try:
        response = ga_service.search(
            customer_id=customer_id,
            query=query
        )
        
        campaigns_billing = []
        for row in response:
            campaign = {
                "campaign_id": row.campaign.id,
                "campaign_name": row.campaign.name,
                "billing_amount": float(row.metrics.cost_micros) / 1000000,  # Convert micros to actual currency
                "status": row.campaign.status.name
            }
            campaigns_billing.append(campaign)
            
        return campaigns_billing
        
    except RefreshError as re:
        return {
            "error": "AUTHENTICATION_ERROR",
            "message": "Refresh token has expired or is invalid. Please reauthenticate.",
            "technical_detail": str(re)
        }, 401
    except google_exceptions.PermissionDenied as pe:
        return {
            "error": "PERMISSION_DENIED",
            "message": "Invalid credentials or insufficient permissions",
            "technical_detail": str(pe)
        }, 403
    except GoogleAdsException as ex:
        return {
            "error": ex.error.code().name,
            "message": ex.failure.errors[0].message,
            "request_id": ex.request_id
        }, 400

@app.route("/")
def index():
    return "Google Ads Billing API"

@app.route("/customer-billing/<customer_id>", methods=['GET'])
def get_customer_billing(customer_id):
    try:
        # Load the Google Ads client
        client = GoogleAdsClient.load_from_storage("google-ads.yaml")
        
        # Get date range for last month
        start_date, end_date = get_last_month_date_range()
        
        # Get billing data
        billing_data = get_campaign_billing(client, customer_id, start_date, end_date)
        
        if isinstance(billing_data, tuple):  # Error case
            return billing_data
        
        return jsonify({
            "customer_id": customer_id,
            "billing_period": {
                "start_date": start_date,
                "end_date": end_date
            },
            "campaigns": billing_data,
            "total_billing": sum(campaign["billing_amount"] for campaign in billing_data)
        })
        
    except Exception as e:
        return {
            "error": "Internal Server Error",
            "message": str(e)
        }, 500

@app.route("/webhook/customer-billing", methods=['POST'])
def webhook_customer_billing():
    try:
        # Validate request payload
        payload = request.get_json()
        if not payload or 'customer_ids' not in payload:
            return {
                "error": "Invalid payload",
                "message": "customer_ids field is required"
            }, 400

        # Load the Google Ads client
        client = GoogleAdsClient.load_from_storage("google-ads.yaml")
        
        # Get date range for last month
        start_date, end_date = get_last_month_date_range()
        
        # Process all customer IDs
        results = []
        for customer_id in payload['customer_ids']:
            try:
                billing_data = get_campaign_billing(client, customer_id, start_date, end_date)
                
                if isinstance(billing_data, tuple):  # Error case
                    customer_result = {
                        "customer_id": customer_id,
                        "status": "error",
                        "error_detail": billing_data[0]
                    }
                else:
                    customer_result = {
                        "customer_id": customer_id,
                        "billing_period": {
                            "start_date": start_date,
                            "end_date": end_date
                        },
                        "campaigns": billing_data,
                        "total_billing": sum(campaign["billing_amount"] for campaign in billing_data),
                        "status": "success"
                    }
            except Exception as ex:
                customer_result = {
                    "customer_id": customer_id,
                    "status": "error",
                    "error_detail": str(ex)
                }
            
            results.append(customer_result)
        
        return jsonify({
            "billing_period": {
                "start_date": start_date,
                "end_date": end_date
            },
            "results": results,
            "processed_count": len(results),
            "success_count": sum(1 for r in results if r["status"] == "success"),
            "error_count": sum(1 for r in results if r["status"] == "error")
        })
        
    except Exception as e:
        return {
            "error": "Internal Server Error",
            "message": str(e)
        }, 500

if __name__ == "__main__":
    app.run(debug=True)