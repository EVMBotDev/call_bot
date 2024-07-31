import os
import json
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram import Bot, ParseMode
from PIL import Image
import requests
from io import BytesIO
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options

load_dotenv()
# Load environment variables
bot_api = os.getenv('BOT_API')

if not bot_api:
    raise ValueError("The BOT_API environment variable is not set")

bot = Bot(token=bot_api)

# Function to read messages log from messages.json
def read_messages_log():
    try:
        with open('messages.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []

# Function to write messages log to messages.json
def write_messages_log(log_data):
    try:
        with open('messages.json', 'w') as file:
            json.dump(log_data, file, indent=4)
    except Exception as e:
        print(f"Error writing to messages.json: {e}")

# Function to add an entry to the messages log
def add_to_messages_log(address):
    messages_log = read_messages_log()
    new_entry = {
        "address": address,
        "posted_at": datetime.now().isoformat()
    }
    messages_log.append(new_entry)
    print(f"Adding to messages log: {new_entry}")  # Debugging line
    write_messages_log(messages_log)

def get_chat_ids():
    updates = bot.get_updates()
    chat_ids = set()
   
    for update in updates:
        if update.message:
            chat_id = update.message.chat_id
            chat_name = update.message.chat.title if update.message.chat.title else "Private Chat"
            chat_ids.add(chat_id)
    return chat_ids

# Function to extract the actual image URL from the HTML response using Selenium
def extract_image_url_with_selenium(url):
    options = Options()
    options.headless = True
    driver = webdriver.Firefox(options=options)
    driver.get(url)
    time.sleep(5)  # Wait for the page to fully load
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    og_image = soup.find('meta', property='og:image')
    driver.quit()
    if og_image:
        return og_image['content']
    return None

# Function to download and save the image
def download_image(url, resolution=(300, 300)):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive'
    }
    try:
        print(f"Downloading image from {url}")
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            img = Image.open(BytesIO(response.content))
            # print(f"Original image format: {img.format}, size: {img.size}, mode: {img.mode}")

            if img.format != 'JPEG' or img.size != resolution:
                img = img.resize(resolution, Image.ANTIALIAS)
                if img.mode == 'RGBA':
                    img = img.convert('RGB')  # Convert RGBA to RGB
                img_byte_arr = BytesIO()
                img.save(img_byte_arr, format='JPEG')
                img_byte_arr.seek(0)
                return img_byte_arr
            else:
                return BytesIO(response.content)
        else:
            print(f"Error downloading image: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error processing image: {e}")
        return None
    

# Function to send a message to a specified chat
def send_message(chat_id, text, metadata):
    photo_url = metadata.get('image')
    token_address = metadata.get('address')
    try:
        if photo_url:
            image_data = download_image(photo_url)
            if image_data:
                bot.send_photo(chat_id=chat_id, photo=image_data, caption=text, parse_mode=ParseMode.MARKDOWN)
            else:
                print("Error resizing image.")
                bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        else:
            bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    except Exception as e:
        print(f"Error sending message: {e}")

# Function to format the message with the collected data
def format_message(metadata):
    fields = {
        "Name": metadata.get('name'),
        "Symbol": metadata.get('symbol'),
        "Address": metadata.get('address'),
        "Supply": metadata.get('supply'),
        "Decimals": metadata.get('decimals'),
        "Owner": metadata.get('owner'),
        "Website": metadata.get('website'),
        "Twitter": metadata.get('twitter'),
        "Telegram": metadata.get('telegram'),
        "Pump.Fun": metadata.get('pump_fun')
    }
    
    message = "*Token Information:*\n\n"
    links = []
    for key, value in fields.items():
        if value:
            if key == "Symbol":
                message += f"*{key}:* ${value}\n\n"
            elif key == "Address":
                message += f"*{key}:* [Solscan](https://solscan.io/token/{value})\n"
            elif key in ["Website", "Twitter", "Telegram", "Pump.Fun"]:
                links.append(f"[{key}]({value})\n")
            else:
                message += f"*{key}:* {value}\n"
            if key in ["Symbol", "Decimals"]:
                message += "\n"
    
    # Include top 5 accounts
    largest_accounts = metadata.get('largest_accounts', [])
    supply = metadata.get('supply')
    decimals = metadata.get('decimals')
    
    if largest_accounts and supply and decimals is not None:
        supply_actual = supply
        
        message += "\n*Top Accounts:*\n"
        account_count = 0
        for account in largest_accounts:
            if account_count >= 6:
                break
            
            account_address = account.get('address')
            account_balance = account.get('balance')
            if account_address and account_balance is not None:
                account_balance_actual = account_balance
                balance_percentage = (account_balance_actual / supply_actual) * 100
                
                if balance_percentage > 10 or balance_percentage <= 1:
                    continue
                
                account_count += 1
                message += f"[{balance_percentage:.2f}%](https://solscan.io/account/{account_address}) - "
    
    if message.endswith(" - "):
        message = message[:-3]

    bonding_curve_progress = metadata.get('bonding_curve_progress')
    one_hour_volume = float(metadata.get('one_hour_volume'))
    market_cap = float(metadata.get('market_cap'))
    liquidity = float(metadata.get('liquidity'))

    formatted_mcap = "${:,.2f}".format(market_cap)
    formatted_hour_volume = "${:,.2f}".format(one_hour_volume)
    formatted_liquidity = "${:,.2f}".format(liquidity)

    if bonding_curve_progress:
        message += f"\n\n*Bonding Curve:* {bonding_curve_progress}\n\n"
    if market_cap:
        message += f"\n\n*Market Cap:* {formatted_mcap}\n\n"
    if one_hour_volume:
        message += f"*1 Hour Volume:* {formatted_hour_volume}\n\n"
    if liquidity:
        message += f"*Liquidity:* {formatted_liquidity}\n\n"

    return message

def post_token_message(metadata):
    address = metadata.get('address')

    if not address:
        print("Metadata does not contain an address.")
        return

    now = datetime.now()
    messages_log = read_messages_log()
    
    # Check if the address has been posted in the last 3 minutes
    for entry in messages_log:
        if entry['address'] == address:
            posted_at = datetime.fromisoformat(entry['posted_at'])
            print(f"Token {address} was last posted at {posted_at}")
            if now - posted_at < timedelta(minutes=3):
                print(f"Token {address} was posted in the last 10 minutes.")
                return

    # Check if any message was posted in the last 60 seconds
    if messages_log:
        last_entry = messages_log[-1]
        last_posted_at = datetime.fromisoformat(last_entry['posted_at'])
        print(f"Last message was posted at {last_posted_at}")
        if now - last_posted_at < timedelta(seconds=60):
            print("A message was posted in the last 60 seconds.")
            return

    message = format_message(metadata)
    chat_ids = get_chat_ids()

    for chat_id in chat_ids:
        send_message(chat_id, message, metadata)
        print(f"Message sent to chat_id {chat_id} with address {address}")

    add_to_messages_log(address)