from google_auth_oauthlib.flow import InstalledAppFlow

def get_refresh_token():
    # Path to your credentials.json file (same directory as script)
    client_secrets_path = "./credentials.json" 

    # Specify the scopes required for Google Ads API
    scopes = ["https://www.googleapis.com/auth/adwords"]

    # Run local server for user authentication
    flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, scopes)
    credentials = flow.run_local_server(port=8080)

    # Print the refresh token
    print("Refresh Token:", credentials.refresh_token)

if __name__ == "__main__":
    get_refresh_token()
