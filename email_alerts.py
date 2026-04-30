#!/usr/bin/env python3
"""
Email Alert Manager for Crowd Detection System
Handles SMTP email notifications when thresholds are exceeded
"""

import smtplib
import json
import time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path


class EmailAlertManager:
    """Manage email alerts for crowd detection events"""
    
    def __init__(self, config_file='smtp_config.json'):
        """Initialize email alert manager
        
        Args:
            config_file: Path to SMTP configuration file
        """
        self.config_file = config_file
        self.config = self._load_config()
        self.last_alert_time = {}
        self.cooldown_seconds = 300  # 5 minute cooldown
        
    def _load_config(self):
        """Load SMTP configuration from file"""
        try:
            if Path(self.config_file).exists():
                with open(self.config_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️  Could not load email config: {e}")
        
        # Return default config if file not found
        return {
            'enabled': False,
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'sender_email': '',
            'sender_password': '',
            'recipient_emails': [],
            'use_tls': True
        }
    
    def save_config(self, config):
        """Save SMTP configuration to file
        
        Args:
            config: Configuration dictionary
        """
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            self.config = config
            return True
        except Exception as e:
            print(f"❌ Error saving email config: {e}")
            return False
    
    def is_enabled(self):
        """Check if email alerts are enabled"""
        return self.config.get('enabled', False)
    
    def is_configured(self):
        """Check if email is properly configured"""
        required = ['sender_email', 'sender_password', 'recipient_emails']
        return all(self.config.get(field) for field in required)
    
    def _should_send_alert(self, alert_key):
        """Check if enough time has passed to send another alert
        
        Args:
            alert_key: Unique identifier for the alert (e.g., zone name)
            
        Returns:
            bool: True if alert should be sent, False if in cooldown
        """
        now = time.time()
        last_alert = self.last_alert_time.get(alert_key, 0)
        
        if now - last_alert > self.cooldown_seconds:
            self.last_alert_time[alert_key] = now
            return True
        
        return False
    
    def send_crowd_alert(self, zone_name, current_count, threshold, metadata=None):
        """Send alert for crowd threshold exceeded
        
        Args:
            zone_name: Name of the zone/location
            current_count: Current crowd count
            threshold: Threshold that was exceeded
            metadata: Additional metadata (optional)
            
        Returns:
            bool: True if email was sent, False otherwise
        """
        if not self.is_enabled() or not self.is_configured():
            return False
        
        alert_key = f"crowd_{zone_name}"
        if not self._should_send_alert(alert_key):
            return False
        
        try:
            subject = f"🚨 CROWD ALERT: {zone_name}"
            
            body = f"""
CROWD DETECTION ALERT
{'='*50}

Zone/Location: {zone_name}
Current Count: {current_count} people
Threshold: {threshold} people
Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Status: ⚠️ THRESHOLD EXCEEDED
Excess: {max(0, current_count - threshold)} people above threshold

"""
            if metadata:
                body += f"\nAdditional Information:\n"
                for key, value in metadata.items():
                    body += f"  {key}: {value}\n"
            
            body += f"""
{'='*50}
Action Required: Please check the monitoring system.

This is an automated alert from DeepVision Crowd Detection System.
"""
            
            return self._send_email(subject, body)
        
        except Exception as e:
            print(f"❌ Error preparing crowd alert: {e}")
            return False
    
    def send_panic_alert(self, panic_level, location, metadata=None):
        """Send alert for high panic level
        
        Args:
            panic_level: Panic level (0-100)
            location: Location/zone name
            metadata: Additional metadata (optional)
            
        Returns:
            bool: True if email was sent, False otherwise
        """
        if not self.is_enabled() or not self.is_configured():
            return False
        
        alert_key = f"panic_{location}"
        if not self._should_send_alert(alert_key):
            return False
        
        try:
            subject = f"🚨 PANIC ALERT: {location}"
            
            body = f"""
PANIC LEVEL ALERT
{'='*50}

Location: {location}
Panic Level: {panic_level}%
Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Status: ⚠️ HIGH PANIC DETECTED
Assessment: {self._get_panic_assessment(panic_level)}

"""
            if metadata:
                body += f"\nMetrics:\n"
                for key, value in metadata.items():
                    body += f"  {key}: {value}\n"
            
            body += f"""
{'='*50}
Action Required: High panic levels detected. Check monitoring system immediately.

This is an automated alert from DeepVision Crowd Detection System.
"""
            
            return self._send_email(subject, body)
        
        except Exception as e:
            print(f"❌ Error preparing panic alert: {e}")
            return False
    
    def send_custom_alert(self, subject, message, recipient_list=None):
        """Send custom alert message
        
        Args:
            subject: Email subject
            message: Email body message
            recipient_list: Optional list of recipients (uses default if None)
            
        Returns:
            bool: True if email was sent, False otherwise
        """
        if not self.is_enabled() or not self.is_configured():
            return False
        
        try:
            return self._send_email(subject, message, recipient_list)
        except Exception as e:
            print(f"❌ Error sending custom alert: {e}")
            return False
    
    def _send_email(self, subject, body, recipient_list=None):
        """Send email via SMTP
        
        Args:
            subject: Email subject
            body: Email body
            recipient_list: Recipients (uses default if None)
            
        Returns:
            bool: True if email was sent successfully
        """
        try:
            sender = self.config.get('sender_email')
            password = self.config.get('sender_password')
            recipients = recipient_list or self.config.get('recipient_emails', [])
            smtp_server = self.config.get('smtp_server', 'smtp.gmail.com')
            smtp_port = self.config.get('smtp_port', 587)
            use_tls = self.config.get('use_tls', True)
            
            if not sender or not password or not recipients:
                print("❌ Email configuration incomplete")
                return False
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = sender
            msg['To'] = ', '.join(recipients) if isinstance(recipients, list) else recipients
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                if use_tls:
                    server.starttls()
                server.login(sender, password)
                server.send_message(msg)
            
            print(f"✅ Alert email sent: {subject}")
            return True
        
        except smtplib.SMTPAuthenticationError:
            print("❌ SMTP Authentication Failed - Check credentials")
            return False
        except smtplib.SMTPException as e:
            print(f"❌ SMTP Error: {e}")
            return False
        except Exception as e:
            print(f"❌ Error sending email: {e}")
            return False
    
    def test_connection(self):
        """Test SMTP connection
        
        Returns:
            bool: True if connection successful
        """
        if not self.is_configured():
            print("❌ Email not properly configured")
            return False
        
        try:
            sender = self.config.get('sender_email')
            password = self.config.get('sender_password')
            smtp_server = self.config.get('smtp_server', 'smtp.gmail.com')
            smtp_port = self.config.get('smtp_port', 587)
            use_tls = self.config.get('use_tls', True)
            
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                if use_tls:
                    server.starttls()
                server.login(sender, password)
            
            print("✅ SMTP connection successful")
            return True
        
        except Exception as e:
            print(f"❌ SMTP connection failed: {e}")
            return False
    
    def send_test_email(self):
        """Send a test email
        
        Returns:
            bool: True if test email was sent
        """
        subject = "DeepVision Test Email"
        body = f"""
This is a test email from DeepVision Crowd Detection System.

Test sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

If you received this email, your SMTP configuration is working correctly!
"""
        return self._send_email(subject, body)
    
    @staticmethod
    def _get_panic_assessment(panic_level):
        """Get assessment text for panic level
        
        Args:
            panic_level: Panic level percentage (0-100)
            
        Returns:
            str: Assessment text
        """
        if panic_level < 20:
            return "🟢 Low - Normal crowd behavior"
        elif panic_level < 40:
            return "🟡 Moderate - Some concern"
        elif panic_level < 60:
            return "🟠 High - Significant concern"
        elif panic_level < 80:
            return "🔴 Very High - Urgent attention needed"
        else:
            return "🔴 Critical - Emergency response recommended"


# Example usage
if __name__ == "__main__":
    # Create manager
    manager = EmailAlertManager()
    
    # Configure (example)
    test_config = {
        'enabled': True,
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'sender_email': 'your_email@gmail.com',
        'sender_password': 'your_app_password',
        'recipient_emails': ['admin@example.com'],
        'use_tls': True
    }
    
    manager.save_config(test_config)
    
    # Test connection
    manager.test_connection()
    
    # Send test email
    manager.send_test_email()
    
    # Send crowd alert
    manager.send_crowd_alert('Main Entrance', 150, 100, {'density': '45%', 'movement': '0.85'})
