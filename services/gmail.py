import os
import base64
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import settings
from db.models import Email, EmailStatus
from db.database import SessionLocal
import logging

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Gmail and Tasks API scopes (shared with Tasks service)
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/tasks'
]


class GmailService:
    def __init__(self):
        self.service = None
        self.credentials = None

    def _ensure_service(self):
        if self.service is None:
            self._authenticate()

    def _authenticate(self):
        """Authenticate with Gmail API using OAuth2"""
        creds = None
        token_path = self._resolve_path(settings.google_token_file)
        credentials_path = self._resolve_path(settings.google_credentials_file)
        
        # Load existing credentials
        if token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            except Exception as e:
                logger.error(f"Error loading credentials: {e}")
        
        # If there are no (valid) credentials available, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.error(f"Error refreshing credentials: {e}")
                    creds = None
            
            if not creds:
                if not credentials_path.exists():
                    raise FileNotFoundError(
                        f"Google credentials file not found: {credentials_path}. "
                        "Please run configure_google.py first."
                    )
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_path), SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            with open(token_path, 'w', encoding='utf-8') as token:
                token.write(creds.to_json())
        
        self.credentials = creds
        self.service = build('gmail', 'v1', credentials=creds)
        logger.info("Gmail API authenticated successfully")

    @staticmethod
    def _resolve_path(path_value: str) -> Path:
        candidate = Path(path_value)
        if candidate.is_absolute():
            return candidate
        return PROJECT_ROOT / candidate
    
    def get_recent_emails(self, max_results: int = 50, hours_back: int = 24) -> List[Dict[str, Any]]:
        """
        Fetch recent emails from Gmail
        
        Args:
            max_results: Maximum number of emails to fetch
            hours_back: How many hours back to search
        
        Returns:
            List of email dictionaries
        """
        try:
            self._ensure_service()

            # Calculate date filter
            since_date = datetime.now() - timedelta(hours=hours_back)
            date_filter = since_date.strftime('%Y/%m/%d')
            
            # Build query
            query_parts = [f'after:{date_filter}']

            status_filters = []
            if settings.process_unread_only:
                status_filters.append("is:unread")

            if settings.process_starred_emails:
                status_filters.append("is:starred")

            if len(status_filters) == 1:
                query_parts.append(status_filters[0])
            elif len(status_filters) > 1:
                query_parts.append(f"({' OR '.join(status_filters)})")
            
            query = ' '.join(query_parts)
            
            # Search for messages
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            
            if not messages:
                logger.info("No messages found")
                return []
            
            logger.info(f"Found {len(messages)} messages")
            
            # Fetch full message details
            emails = []
            for message in messages:
                try:
                    email_data = self._get_message_details(message['id'])
                    if email_data:
                        emails.append(email_data)
                except Exception as e:
                    logger.error(f"Error processing message {message['id']}: {e}")
                    continue
            
            return emails
            
        except HttpError as error:
            logger.error(f"Gmail API error: {error}")
            return []
        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            return []
    
    def _get_message_details(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific message"""
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            # Extract headers
            headers = {}
            for header in message['payload'].get('headers', []):
                headers[header['name'].lower()] = header['value']
            
            # Extract body
            body = self._extract_message_body(message['payload'])
            
            # Parse date
            received_at = self._parse_email_date(headers.get('date', ''))
            
            return {
                'gmail_id': message_id,
                'thread_id': message.get('threadId'),
                'sender': headers.get('from', 'Unknown'),
                'subject': headers.get('subject', 'No Subject'),
                'body': body,
                'received_at': received_at,
                'labels': message.get('labelIds', [])
            }
            
        except Exception as e:
            logger.error(f"Error getting message details for {message_id}: {e}")
            return None
    
    def _extract_message_body(self, payload: Dict[str, Any]) -> str:
        """Extract text body from email payload"""
        body = ""
        
        if 'parts' in payload:
            # Multipart message
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    if 'data' in part['body']:
                        body += base64.urlsafe_b64decode(
                            part['body']['data']
                        ).decode('utf-8', errors='replace')
                elif part['mimeType'] == 'text/html' and not body:
                    # Fallback to HTML if no plain text
                    if 'data' in part['body']:
                        body += base64.urlsafe_b64decode(
                            part['body']['data']
                        ).decode('utf-8', errors='replace')
        else:
            # Single part message
            if payload['mimeType'] in ['text/plain', 'text/html']:
                if 'data' in payload['body']:
                    body = base64.urlsafe_b64decode(
                        payload['body']['data']
                    ).decode('utf-8', errors='replace')
        
        return body[:5000]  # Limit body length
    
    def _parse_email_date(self, date_str: str) -> datetime:
        """Parse email date string to datetime"""
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except:
            return datetime.now()
    
    def save_emails_to_db(self, emails: List[Dict[str, Any]]) -> List[int]:
        """Save emails to database"""
        db = SessionLocal()
        email_ids = []
        
        try:
            for email_data in emails:
                # Check if email already exists
                existing = db.query(Email).filter(
                    Email.gmail_id == email_data['gmail_id']
                ).first()
                
                if not existing:
                    email = Email(
                        gmail_id=email_data['gmail_id'],
                        thread_id=email_data['thread_id'],
                        sender=email_data['sender'],
                        subject=email_data['subject'],
                        body=email_data['body'],
                        received_at=email_data['received_at'],
                        status=EmailStatus.UNPROCESSED
                    )
                    db.add(email)
                    db.flush()  # Get the ID
                    email_ids.append(email.id)
                else:
                    email_ids.append(existing.id)
            
            db.commit()
            logger.info(f"Saved {len(email_ids)} emails to database")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error saving emails to database: {e}")
            raise
        finally:
            db.close()
        
        return email_ids
    
    def mark_email_as_read(self, gmail_id: str):
        """Mark email as read in Gmail"""
        try:
            self._ensure_service()
            self.service.users().messages().modify(
                userId='me',
                id=gmail_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
        except Exception as e:
            logger.error(f"Error marking email as read: {e}")
    
    def send_email(self, to: str, subject: str, body: str, html_body: str = None):
        """Send an email"""
        try:
            self._ensure_service()
            message = MIMEMultipart('alternative')
            message['to'] = to
            message['subject'] = subject
            
            # Add plain text part
            text_part = MIMEText(body, 'plain')
            message.attach(text_part)
            
            # Add HTML part if provided
            if html_body:
                html_part = MIMEText(html_body, 'html')
                message.attach(html_part)
            
            # Send the message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            self.service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            logger.info(f"Email sent successfully to {to}")
            
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            raise
    
    def get_user_profile(self) -> Dict[str, Any]:
        """Get Gmail user profile information"""
        try:
            self._ensure_service()
            profile = self.service.users().getProfile(userId='me').execute()
            return {
                'email': profile.get('emailAddress'),
                'messages_total': profile.get('messagesTotal', 0),
                'threads_total': profile.get('threadsTotal', 0)
            }
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return {}
    
    def test_connection(self) -> Dict[str, Any]:
        """Test Gmail API connection"""
        try:
            profile = self.get_user_profile()
            if profile.get('email'):
                return {
                    'status': 'success',
                    'message': f"Connected to Gmail: {profile['email']}",
                    'profile': profile
                }
            else:
                return {
                    'status': 'error',
                    'message': 'Failed to get user profile'
                }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Gmail connection failed: {str(e)}'
            }
