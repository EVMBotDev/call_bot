import time
import logging
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Set up Firefox options
options = Options()
options.headless = True
driver = webdriver.Firefox(options=options)

def scrape_pump_fun(url, token_address):
    try:
        # Load the page
        driver.get(url)

        time.sleep(5)  # Wait for the page to fully load (adjust as needed)

        # Extract bonding curve progress
        bonding_curve_progress = None
        bonding_curve_progress_elements = driver.find_elements(By.XPATH, "//div[contains(text(), 'bonding curve progress')]")
        for elem in bonding_curve_progress_elements:
            bonding_curve_progress_text = elem.get_attribute('innerHTML').strip()  # Use innerHTML instead of text
            if 'bonding curve progress' in bonding_curve_progress_text:
                parts = bonding_curve_progress_text.split(': ')
                if len(parts) == 2:
                    bonding_curve_progress = parts[1]
                else:
                    logging.error(f"Invalid bonding curve progress text format: {bonding_curve_progress_text}")
                break
        else:
            logging.error("Bonding curve progress text not found in elements.")

        # Check if bonding curve progress is 100%
        if bonding_curve_progress == '100%':
            logging.info("Bonding curve progress is 100%, using API data instead.")
            return get_data_from_api(token_address)

        # Extract market cap
        market_cap = None
        market_cap_elements = driver.find_elements(By.XPATH, "//div[contains(text(), 'Market cap')]")
        for elem in market_cap_elements:
            market_cap_text = elem.text
            if 'Market cap' in market_cap_text:
                market_cap = market_cap_text.split(': ')[1]
                break
        else:
            logging.error("Market cap text not found in elements.")

        # Return the extracted data
        if bonding_curve_progress and market_cap:
            data = {
                'bonding_curve_progress': bonding_curve_progress,
                'market_cap': market_cap
            }
            logging.info(f"Data retrieved from pump.fun: {data}")

            # Write the extracted data to the text file
            # with open('pump_fun_page.txt', 'a', encoding='utf-8') as file:
            #     file.write("\nExtracted Data:\n")
            #     file.write(str(data))
            
            return data
        else:
            logging.error("Required data not found for token address: {token_address}")
            return None

    except Exception as e:
        logging.error(f"Error during web scraping: {e}")
        # Write the error to pump_fun_page.txt
        with open('pump_fun_page.txt', 'a', encoding='utf-8') as file:
            file.write(f"\nError during web scraping: {e}")
        return None

def get_data_from_api(token_address):
    url = f'https://api.geckoterminal.com/api/v2/networks/solana/tokens/{token_address}/pools?page=1'
    headers = {'accept': 'application/json'}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        # Write the data to pump_fun_page.txt
        # with open('pump_fun_page.txt', 'a', encoding='utf-8') as file:
        #     file.write("\nAPI Data:\n")
        #     file.write(json.dumps(data, indent=4))

        extracted_data = {
            'one_hour_volume': data['data'][0]['attributes']['volume_usd']['h1'],
            'market_cap': data['data'][0]['attributes']['fdv_usd'],
            'liquidity': data['data'][0]['attributes']['reserve_in_usd']
        }
        logging.info(f"Data retrieved from API: {extracted_data}")
        return extracted_data
    except Exception as e:
        logging.error(f"API request error: {e}")
        # Write the error to pump_fun_page.txt
        with open('pump_fun_page.txt', 'a', encoding='utf-8') as file:
            file.write(f"\nAPI request error: {e}")
        return None
