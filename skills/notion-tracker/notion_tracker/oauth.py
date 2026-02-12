"""
Notion OAuth handler for authentication flow.
"""
import json
import os
import time
import webbrowser
from typing import Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, parse_qs
import threading

from .models import OAuthTokenData


class OAuthHandler:
    """Handles Notion OAuth authentication flow."""

    TOKEN_FILE = os.path.expanduser("~/.notion_tokens.json")

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str = "http://localhost:8080/callback"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.auth_url = "https://api.notion.com/v1/oauth/authorize"
        self.token_url = "https://api.notion.com/v1/oauth/token"

    def get_authorization_url(self) -> str:
        """Generate OAuth authorization URL."""
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "owner": "user",
        }
        return f"{self.auth_url}?{urlencode(params)}"

    def open_auth_page(self) -> str:
        """Open browser for OAuth authorization."""
        url = self.get_authorization_url()
        print(f"Opening Notion authorization page...")
        webbrowser.open(url)
        return url

    def exchange_code_for_token(self, authorization_code: str) -> OAuthTokenData:
        """Exchange authorization code for access token."""
        import requests

        auth = (self.client_id, self.client_secret)
        data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": self.redirect_uri,
        }

        response = requests.post(
            self.token_url,
            auth=auth,
            data=data,
            headers={"Notion-Version": "2022-06-28"}
        )

        if response.status_code != 200:
            raise ValueError(f"Token exchange failed: {response.text}")

        token_data = response.json()
        return OAuthTokenData(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_in=token_data.get("expires_in", 3600),
            issued_at=int(time.time()),
            token_type=token_data.get("token_type", "bearer")
        )

    def refresh_access_token(self, refresh_token: str) -> OAuthTokenData:
        """Refresh an expired access token."""
        import requests

        auth = (self.client_id, self.client_secret)
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        response = requests.post(
            self.token_url,
            auth=auth,
            data=data,
            headers={"Notion-Version": "2022-06-28"}
        )

        if response.status_code != 200:
            raise ValueError(f"Token refresh failed: {response.text}")

        token_data = response.json()
        return OAuthTokenData(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_in=token_data.get("expires_in", 3600),
            issued_at=int(time.time()),
            token_type=token_data.get("token_type", "bearer")
        )

    def save_tokens(self, token_data: OAuthTokenData) -> None:
        """Save token data to file."""
        with open(self.TOKEN_FILE, 'w') as f:
            json.dump(token_data.model_dump(), f, indent=2)
        print(f"Tokens saved to {self.TOKEN_FILE}")

    def load_tokens(self) -> Optional[OAuthTokenData]:
        """Load token data from file."""
        if not os.path.exists(self.TOKEN_FILE):
            return None

        try:
            with open(self.TOKEN_FILE, 'r') as f:
                data = json.load(f)
            return OAuthTokenData(**data)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Failed to load tokens: {e}")
            return None

    def get_valid_access_token(self) -> Optional[str]:
        """Get valid access token, refreshing if necessary."""
        token_data = self.load_tokens()

        if not token_data:
            return None

        # Check if token is expired or about to expire
        if token_data.issued_at:
            current_time = time.time()
            token_age = current_time - token_data.issued_at
            time_until_expiry = token_data.expires_in - token_age

            if time_until_expiry < 300:  # Less than 5 minutes
                if token_data.refresh_token:
                    try:
                        new_token_data = self.refresh_access_token(token_data.refresh_token)
                        self.save_tokens(new_token_data)
                        return new_token_data.access_token
                    except Exception as e:
                        print(f"Token refresh failed: {e}")
                        return None
                else:
                    return None

        return token_data.access_token

    def clear_tokens(self) -> None:
        """Remove stored tokens."""
        if os.path.exists(self.TOKEN_FILE):
            os.remove(self.TOKEN_FILE)
            print("Tokens cleared")


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback."""

    authorization_code: Optional[str] = None
    server_instance = None

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def do_GET(self):
        """Handle GET request with authorization code."""
        query = parse_qs(self.path.split('?')[1] if '?' in self.path else '')
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        if 'code' in query:
            OAuthCallbackHandler.authorization_code = query['code'][0]
            OAuthCallbackHandler.server_instance.shutdown()
            self.wfile.write(b"<html><body><h1>Authorization successful!</h1><p>You can close this window.</p></body></html>")
        else:
            error = query.get('error', ['Unknown error'])[0]
            self.wfile.write(f"<html><body><h1>Authorization failed</h1><p>Error: {error}</p></body></html>".encode())


def run_oauth_flow() -> str:
    """
    Run full OAuth flow and return access token.

    Returns:
        str: Access token for Notion API
    """
    client_id = os.environ.get("NOTION_CLIENT_ID")
    client_secret = os.environ.get("NOTION_CLIENT_SECRET")
    redirect_uri = os.environ.get("NOTION_REDIRECT_URI", "http://localhost:8080/callback")

    if not client_id or not client_secret:
        raise ValueError("NOTION_CLIENT_ID and NOTION_CLIENT_SECRET must be set")

    handler = OAuthHandler(client_id, client_secret, redirect_uri)

    # Check for existing valid token
    existing_token = handler.get_valid_access_token()
    if existing_token:
        print("Using cached access token")
        return existing_token

    # Open browser for authorization
    handler.open_auth_page()
    print("Please authorize the application in your browser...")
    print(f"Or copy this URL: {handler.get_authorization_url()}")

    # Start local server to receive callback
    OAuthCallbackHandler.server_instance = HTTPServer(('localhost', 8080), OAuthCallbackHandler)
    server_thread = threading.Thread(target=OAuthCallbackHandler.server_instance.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    # Wait for authorization
    OAuthCallbackHandler.server_instance.handle_request()

    # Exchange code for token
    if OAuthCallbackHandler.authorization_code:
        token_data = handler.exchange_code_for_token(OAuthCallbackHandler.authorization_code)
        handler.save_tokens(token_data)
        print("Authorization successful!")
        return token_data.access_token
    else:
        raise ValueError("Authorization code not received")


def get_access_token() -> Optional[str]:
    """
    Get access token from environment or OAuth flow.

    Returns:
        str or None: Access token if available
    """
    # Check for direct access token
    direct_token = os.environ.get("NOTION_ACCESS_TOKEN")
    if direct_token:
        return direct_token

    # Use OAuth
    try:
        return run_oauth_flow()
    except Exception as e:
        print(f"OAuth failed: {e}")
        return None
