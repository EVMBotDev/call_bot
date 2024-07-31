import re
import json
import os
import sol_helper
from msg_sender import send_message, format_message, get_chat_ids, post_token_message

# Regex patterns for Solana and EVM addresses
SOLANA_ADDRESS_PATTERN = r'[1-9A-HJ-NP-Za-km-z]{32,44}'
EVM_ADDRESS_PATTERN = r'0x[a-fA-F0-9]{40}'

def contains_solana_address(message):
    match = re.search(SOLANA_ADDRESS_PATTERN, message)
    if match:
        solana_address = match.group(0)
        try:
            metadata = sol_helper.get_token_metadata(solana_address)
            if metadata:
                metadata['address'] = solana_address  # Add the address to the metadata
                return metadata  # Return metadata instead of True
        except Exception as e:
            print(f"Error fetching token metadata: {e}")
    return False

def contains_evm_address(message):
    match = re.search(EVM_ADDRESS_PATTERN, message)
    if match:
        evm_address = match.group(0)
        metadata = {"address": evm_address}  # Include the address in the metadata
        return metadata
    return False

def is_token_address(message):
    return contains_solana_address(message) or contains_evm_address(message)

def identify_token_type(message):
    if contains_solana_address(message):
        return "Solana"
    elif contains_evm_address(message):
        return "EVM"
    else:
        return "Unknown"

def extract_token_address(message):
    solana_match = re.search(SOLANA_ADDRESS_PATTERN, message)
    if solana_match:
        return solana_match.group(0)
    evm_match = re.search(EVM_ADDRESS_PATTERN, message)
    if evm_match:
        return evm_match.group(0)
    return None

def save_address_message(group_name, address, num_participants, message, metadata):
    token_type = identify_token_type(message)

    # Check if the file exists
    if not os.path.exists('addresses.json'):
        # Create the file with an empty list if it doesn't exist
        with open('addresses.json', 'w') as f:
            json.dump([], f)

    # Save or update message to JSON file
    with open('addresses.json', 'r+') as f:
        try:
            addresses = json.load(f)
        except json.JSONDecodeError:
            addresses = []

        # Check for existing entries
        entry_exists = False
        for entry in addresses:
            if entry['address'] == address:
                # If the address exists, update the entry
                entry_exists = True
                if 'groups' not in entry:
                    entry['groups'] = []
                # Check if the group already exists in the entry
                group_exists = any(g['group_name'] == group_name for g in entry['groups'])
                if not group_exists:
                    entry['groups'].append({
                        'group_name': group_name,
                        'num_participants': num_participants
                    })
                entry['number_groups'] = len(entry['groups'])

                # Update the metadata
                entry.update(metadata)
                break

        if not entry_exists:
            # Append new entry if not found
            new_entry = {
                'address': address,
                'token_type': token_type,
                'number_groups': 1,
                'groups': [{
                    'group_name': group_name,
                    'num_participants': num_participants
                }]
            }
            # Add metadata to the new entry
            new_entry.update(metadata)
            addresses.append(new_entry)

        f.seek(0)
        f.truncate()  # Clear the file before writing
        json.dump(addresses, f, indent=4)

    # Log the message for debugging
    with open('message_log.txt', 'a', encoding='utf-8') as log_file:
        log_file.write(f"Message from group {group_name}:\n{message}\n\n")

    # Format and send the message
    post_token_message(metadata)
