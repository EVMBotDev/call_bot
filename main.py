import os
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.types import MessageEntityTextUrl
import address_helper  # Import the address_helper module
from telethon.errors import ChatAdminRequiredError, ChannelPrivateError
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.messages import GetFullChatRequest
from datetime import datetime
import json

# Load environment variables from .env file
load_dotenv()

# Get the environment variables
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
phone_number = os.getenv('PHONE_NUMBER')
own_chat_id = int(os.getenv('OWN_CHAT_ID'))  # Convert OWN_CHAT_ID to an integer

# Create the client and connect
client = TelegramClient('session_name', api_id, api_hash)

# Variable to store group IDs and names
group_ids = []
group_names = {}

# Add the chat ID to ignore
ignore_chat_ids = {own_chat_id}

# Flag to indicate if a message is being processed
is_processing_message = False

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, bytes):
            return obj.decode('utf-8', errors='ignore')
        return super(CustomJSONEncoder, self).default(obj)

# Event handler for new messages in groups and channels
@client.on(events.NewMessage(chats=group_ids))
async def group_message_handler(event):
    global is_processing_message
    if event.chat_id in ignore_chat_ids or is_processing_message:
        print(f"Ignoring message in chat ID {event.chat_id} currently processing a message")
        return  

    is_processing_message = True  

    group_name = group_names.get(event.chat_id, "Unknown")
    message_text = event.message.message

    metadata = address_helper.contains_solana_address(message_text)
    if metadata or address_helper.contains_evm_address(message_text):
        token_type = address_helper.identify_token_type(message_text)
        address = address_helper.extract_token_address(message_text)
        if address:
            try:
                # Get number of participants/subscribers
                if event.is_channel:
                    full_channel = await client(GetFullChannelRequest(channel=event.chat_id))
                    num_participants = full_channel.full_chat.participants_count
                else:
                    full_chat = await client(GetFullChatRequest(chat_id=event.chat_id))
                    num_participants = full_chat.full_chat.participants_count
            except (ChatAdminRequiredError, ChannelPrivateError):
                # If we don't have permission to get participants, set to unknown
                num_participants = "unknown"
            except Exception as e:
                print(f"Error retrieving participants: {e}")
                num_participants = "unknown"
            
            address_helper.save_address_message(group_name, address, num_participants, message_text, metadata if metadata else {})

    is_processing_message = False  # Reset the flag once message processing is complete

# Event handler for detecting when the user joins a new group or channel
@client.on(events.ChatAction)
async def chat_action_handler(event):
    if event.user_added or event.user_joined:
        if event.user_id == (await client.get_me()).id:  # Check if the event is for the current user
            dialog = await client.get_entity(event.chat_id)
            if dialog.is_group or dialog.is_channel:
                group = {
                    'id': dialog.id,
                    'name': dialog.title,
                    'is_group': dialog.is_group
                }
                group_ids.append(dialog.id)
                group_names[dialog.id] = dialog.title
                with open('groups.json', 'r+') as f:
                    try:
                        groups = json.load(f)
                    except json.JSONDecodeError:
                        groups = []
                    groups.append(group)
                    f.seek(0)
                    json.dump(groups, f, indent=4)
                print(f"Joined new group: {dialog.title}")

async def main():
    # Log in to your account
    await client.start(phone_number)
    print("Client Created")

    # Get all dialogs (chats and groups)
    dialogs = await client.get_dialogs()

    # Extract relevant information
    groups = []
    for dialog in dialogs:
        if dialog.is_group or dialog.is_channel:
            group = {
                'id': dialog.id,
                'name': dialog.name,
                'is_group': dialog.is_group
            }
            groups.append(group)
            group_ids.append(dialog.id)
            group_names[dialog.id] = dialog.name

    # Write the groups to a JSON file
    with open('groups.json', 'w') as f:
        json.dump(groups, f, indent=4)

    print("Groups saved to groups.json")

    # Update the event handler with the group IDs
    client.remove_event_handler(group_message_handler)
    client.add_event_handler(group_message_handler, events.NewMessage(chats=group_ids))

    # Keep the client running
    await client.run_until_disconnected()

if __name__ == '__main__':
    with client:
        client.loop.run_until_complete(main())
