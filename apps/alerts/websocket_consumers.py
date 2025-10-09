"""
WebSocket Consumers for real-time alert notifications
"""

import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)


class AlertConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time alert notifications
    Users connect to receive real-time updates about alerts
    """

    async def connect(self):
        """Handle WebSocket connection"""
        try:
            # Get user from scope (set by authentication middleware)
            self.user = self.scope.get("user")

            if not self.user or not hasattr(self.user, "id"):
                logger.warning("Unauthenticated WebSocket connection attempt")
                await self.close()
                return

            # Create group name based on user ID
            self.user_id = str(self.user.id)
            self.group_name = f"user_{self.user_id}_alerts"

            # Join user's alert group
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )

            # Accept connection
            await self.accept()

            logger.info(f"WebSocket connected for user {self.user_id}")

            # Send connection confirmation
            await self.send(text_data=json.dumps({
                "type": "connection_established",
                "message": "Connected to alert notifications",
            }))

        except Exception as e:
            logger.error(f"Error in WebSocket connect: {e}", exc_info=True)
            await self.close()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        try:
            # Leave user's alert group
            if hasattr(self, "group_name"):
                await self.channel_layer.group_discard(
                    self.group_name,
                    self.channel_name
                )

            logger.info(f"WebSocket disconnected for user {getattr(self, 'user_id', 'unknown')}")

        except Exception as e:
            logger.error(f"Error in WebSocket disconnect: {e}", exc_info=True)

    async def receive(self, text_data):
        """Handle messages from WebSocket"""
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "ping":
                # Respond to ping
                await self.send(text_data=json.dumps({
                    "type": "pong",
                }))

            elif message_type == "subscribe_company":
                # Subscribe to company-wide alerts
                company_id = data.get("company_id")
                if company_id:
                    await self.subscribe_to_company(company_id)

            elif message_type == "subscribe_team":
                # Subscribe to team-specific alerts
                team_id = data.get("team_id")
                if team_id:
                    await self.subscribe_to_team(team_id)

            elif message_type == "unsubscribe":
                # Unsubscribe from specific groups
                group_type = data.get("group_type")
                group_id = data.get("group_id")
                if group_type and group_id:
                    await self.unsubscribe_from_group(group_type, group_id)

            else:
                logger.warning(f"Unknown message type: {message_type}")

        except json.JSONDecodeError:
            logger.error("Invalid JSON received from WebSocket")
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}", exc_info=True)

    async def subscribe_to_company(self, company_id):
        """Subscribe to company-wide alerts"""
        try:
            # Verify user has access to this company
            has_access = await self.verify_company_access(company_id)

            if has_access:
                group_name = f"company_{company_id}_alerts"
                await self.channel_layer.group_add(
                    group_name,
                    self.channel_name
                )

                await self.send(text_data=json.dumps({
                    "type": "subscribed",
                    "group_type": "company",
                    "group_id": company_id,
                }))

                logger.info(f"User {self.user_id} subscribed to company {company_id} alerts")

        except Exception as e:
            logger.error(f"Error subscribing to company alerts: {e}", exc_info=True)

    async def subscribe_to_team(self, team_id):
        """Subscribe to team-specific alerts"""
        try:
            # Verify user has access to this team
            has_access = await self.verify_team_access(team_id)

            if has_access:
                group_name = f"team_{team_id}_alerts"
                await self.channel_layer.group_add(
                    group_name,
                    self.channel_name
                )

                await self.send(text_data=json.dumps({
                    "type": "subscribed",
                    "group_type": "team",
                    "group_id": team_id,
                }))

                logger.info(f"User {self.user_id} subscribed to team {team_id} alerts")

        except Exception as e:
            logger.error(f"Error subscribing to team alerts: {e}", exc_info=True)

    async def unsubscribe_from_group(self, group_type, group_id):
        """Unsubscribe from a specific group"""
        try:
            group_name = f"{group_type}_{group_id}_alerts"
            await self.channel_layer.group_discard(
                group_name,
                self.channel_name
            )

            await self.send(text_data=json.dumps({
                "type": "unsubscribed",
                "group_type": group_type,
                "group_id": group_id,
            }))

        except Exception as e:
            logger.error(f"Error unsubscribing from group: {e}", exc_info=True)

    @database_sync_to_async
    def verify_company_access(self, company_id):
        """Verify user has access to company"""
        # Check if user belongs to this company
        return str(self.user.company_id) == str(company_id)

    @database_sync_to_async
    def verify_team_access(self, team_id):
        """Verify user has access to team"""
        # In a real implementation, check team membership
        # For now, just verify company access
        return True

    async def send_alert(self, event):
        """
        Send alert notification to WebSocket
        Called when an alert is triggered
        """
        try:
            # Extract alert data from event
            data = event.get("data", {})

            # Send to WebSocket
            await self.send(text_data=json.dumps(data))

            logger.debug(f"Sent alert notification to user {self.user_id}")

        except Exception as e:
            logger.error(f"Error sending alert to WebSocket: {e}", exc_info=True)

    async def alert_updated(self, event):
        """
        Send alert update notification to WebSocket
        Called when an alert is acknowledged, resolved, or muted
        """
        try:
            data = event.get("data", {})

            await self.send(text_data=json.dumps(data))

            logger.debug(f"Sent alert update to user {self.user_id}")

        except Exception as e:
            logger.error(f"Error sending alert update to WebSocket: {e}", exc_info=True)


class CompanyAlertConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for company-wide alert monitoring
    Admins can connect to monitor all company alerts
    """

    async def connect(self):
        """Handle WebSocket connection"""
        try:
            self.user = self.scope.get("user")

            if not self.user or not hasattr(self.user, "id"):
                await self.close()
                return

            # Verify user is admin
            if not self.user.is_admin():
                logger.warning(f"Non-admin user {self.user.id} attempted to connect to company alerts")
                await self.close()
                return

            # Get company ID from URL
            self.company_id = self.scope["url_route"]["kwargs"]["company_id"]

            # Verify user belongs to this company
            if str(self.user.company_id) != str(self.company_id):
                logger.warning(f"User {self.user.id} attempted to access company {self.company_id} alerts")
                await self.close()
                return

            # Join company alert group
            self.group_name = f"company_{self.company_id}_alerts"
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )

            await self.accept()

            logger.info(f"Admin {self.user.id} connected to company {self.company_id} alerts")

            await self.send(text_data=json.dumps({
                "type": "connection_established",
                "message": f"Connected to company {self.company_id} alert monitoring",
            }))

        except Exception as e:
            logger.error(f"Error in company alert WebSocket connect: {e}", exc_info=True)
            await self.close()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        try:
            if hasattr(self, "group_name"):
                await self.channel_layer.group_discard(
                    self.group_name,
                    self.channel_name
                )

        except Exception as e:
            logger.error(f"Error in company alert WebSocket disconnect: {e}", exc_info=True)

    async def receive(self, text_data):
        """Handle messages from WebSocket"""
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "ping":
                await self.send(text_data=json.dumps({"type": "pong"}))

        except Exception as e:
            logger.error(f"Error handling company alert WebSocket message: {e}", exc_info=True)

    async def send_alert(self, event):
        """Send alert to WebSocket"""
        try:
            data = event.get("data", {})
            await self.send(text_data=json.dumps(data))

        except Exception as e:
            logger.error(f"Error sending company alert to WebSocket: {e}", exc_info=True)
