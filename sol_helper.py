import os
from dotenv import load_dotenv
import requests
import json
import pump_fun_scraper

# Load environment variables from .env file
load_dotenv()

# Get the Solana RPC URL from environment variables
solana_rpc_url = os.getenv('RPC_URL')

if not solana_rpc_url:
    raise ValueError("The RPC_URL environment variable is not set")

def fetch_metadata_from_ipfs(ipfs_uri):
    response = requests.get(ipfs_uri)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Error fetching metadata from IPFS: {response.status_code}, {response.text}")

def get_token_largest_accounts(token_mint_address):
    payload = {
        "jsonrpc": "2.0",
        "id": "my-id",
        "method": "getTokenLargestAccounts",
        "params": [token_mint_address]
    }
    headers = {
        "Content-Type": "application/json"
    }
    response = requests.post(solana_rpc_url, json=payload, headers=headers)
    if response.status_code == 200:
        result = response.json().get("result", {}).get("value", [])
        return result
    else:
        raise Exception(f"Error fetching largest token accounts: {response.status_code}, {response.text}")

def get_token_metadata(token_mint_address):
    payload = {
        "jsonrpc": "2.0",
        "id": "my-id",
        "method": "getAsset",
        "params": {
            "id": token_mint_address,
            "displayOptions": {
                "showFungible": True  # return details about a fungible token
            }
        }
    }
    headers = {
        "Content-Type": "application/json"
    }
    response = requests.post(solana_rpc_url, json=payload, headers=headers)
    if response.status_code == 200:
        result = response.json().get("result", {})
        if result:
            metadata = result.get("content", {}).get("metadata", {})
            token_info = result.get("token_info", {})
            json_uri = result.get("content", {}).get("json_uri")
            additional_metadata = {}
            if json_uri:
                json_uri = json_uri.replace("https://cf-ipfs.com/ipfs/", "https://ipfs.io/ipfs/")
                additional_metadata = fetch_metadata_from_ipfs(json_uri)
            decimals = token_info.get("decimals")
            supply = token_info.get("supply") / (10 ** decimals) if decimals is not None else token_info.get("supply")
            token_metadata = {
                "name": metadata.get("name"),
                "symbol": metadata.get("symbol"),
                "json_uri": json_uri,
                "supply": supply,
                "decimals": decimals,
                "owner": result.get("ownership", {}).get("owner")
            }
            # Merge additional metadata
            token_metadata.update({
                "image": additional_metadata.get("image").replace("https://cf-ipfs.com/ipfs/", "https://ipfs.io/ipfs/") if additional_metadata.get("image") else None,
                "twitter": additional_metadata.get("twitter"),
                "telegram": additional_metadata.get("telegram"),
                "website": additional_metadata.get("website"),
                "pump_fun": "https://pump.fun/" + token_mint_address
            })

            # Fetch and add the largest token accounts
            largest_accounts = get_token_largest_accounts(token_mint_address)
            top_5_accounts = largest_accounts[:5]
            token_metadata["largest_accounts"] = [
                {"address": account["address"], "balance": account["uiAmount"]} for account in top_5_accounts
            ]

            pump_url = token_metadata.get("pump_fun")
            pump_fun_data = pump_fun_scraper.scrape_pump_fun(pump_url, token_mint_address)
            if pump_fun_data:
                token_metadata.update(pump_fun_data)

            return token_metadata
        else:
            return None
    else:
        raise Exception(f"Error fetching token metadata: {response.status_code}, {response.text}")

if __name__ == "__main__":
    # Example usage
    token_mint_address = "ExampleTokenMintAddress"
    metadata = get_token_metadata(token_mint_address)
    print(json.dumps(metadata, indent=4))
