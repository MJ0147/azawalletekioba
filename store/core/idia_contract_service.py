import os
from typing import Any
from base64 import b64encode, b64decode
import requests

try:
    from tonsdk.utils import Address
    from tonsdk.boc import Cell
except Exception:
    Address = None  # type: ignore[assignment]
    Cell = None  # type: ignore[assignment]

IDIA_CONTRACT = "EQC8QIjU-uXwrlj9B9Zc0ZBIaTS5TLzFb6djJIRwyLa6Enqs"


class IdiaContractService:
    def __init__(self, client: Any):
        self.client = client

    def get_token_info(self):
        result = self.client.net.query_collection(
            collection="accounts",
            filter={"id": {"eq": IDIA_CONTRACT}},
            result="balance, code_hash",
        )
        return result

    def get_wallet_address(self, owner_address: str):
        if Address is None or Cell is None:
            return None

        try:
            owner_addr = Address(owner_address)
            builder = Cell.new_builder()
            builder.store_address(owner_addr)
            cell = builder.end_cell()
            boc = b64encode(cell.to_boc(False)).decode('utf-8')

            api_key = os.getenv("TON_API_KEY", "")
            headers = {
                "Content-Type": "application/json",
            }
            if api_key:
                headers["X-API-Key"] = api_key

            data = {
                "address": IDIA_CONTRACT,
                "method": "get_wallet_address",
                "stack": [
                    ["slice", cell.to_boc(False).hex()]
                ]
            }

            # Using a public accessor for runGetMethod
            response = requests.post(f"https://toncenter.com/api/v2/runGetMethod", json=data, headers=headers)
            response.raise_for_status()

            result = response.json().get('result')
            if not result or result.get('exit_code') != 0:
                return None

            # Result stack: [["cell", {"bytes": "..."}]]
            wallet_address_boc = b64decode(result['stack'][0][1]['bytes'])
            wallet_address_cell = Cell.one_from_boc(wallet_address_boc)
            wallet_address = wallet_address_cell.begin_parse().read_address()
            
            return wallet_address.to_string(is_user_friendly=True, is_bounceable=True, is_testnet=False)

        except Exception as e:
            # It's good practice to log the exception
            print(f"Could not get wallet address: {e}")
            return None
