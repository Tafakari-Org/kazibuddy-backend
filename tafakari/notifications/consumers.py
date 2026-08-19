import json
from channels.generic.websocket import AsyncWebsocketConsumer

class AdminNotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        
        # Accept connection only for authenticated admins
        if user.is_authenticated and user.user_type in ['admin', 'super_admin']:
            self.group_name = "admin_notifications"
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            await self.accept()
        else:
            await self.close()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def send_notification(self, event):
        notification = event["notification"]
        await self.send(text_data=json.dumps({
            "type": "notification",
            "data": notification
        }))
