import os
from typing import Any
from base64 import b64encode, b64decode
import requests

try:
    from tonsdk.utils import Address
    from tonsdk.boc import Cell, begin_cell
except Exception:
    Address = None  # type: ignore[assignment]
    Cell = None  # type: ignore[assignment]
    begin_cell = None  # type: ignore[assignment]

IDIA_CONTRACT = os.getenv(
    "IDIA_TON_JETTON_ADDRESS",
    os.getenv("TON_CONTRACT_ADDRESS", "EQC8QIjU-uXwrlj9B9Zc0ZBIaTS5TLzFb6djJIRwyLa6Enqs"),
)
TONCENTER_API_BASE = os.getenv("TON_API_BASE", "https://toncenter.com/api/v2").rstrip("/")


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
        if Address is None or Cell is None or begin_cell is None:
            return None

        try:
            # tonsdk exposes the builder as begin_cell(); Cell has no
            # new_builder(), so the old call always raised.
            cell = begin_cell().store_address(Address(owner_address)).end_cell()
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
                # toncenter expects a base64 BOC tagged "tvm.Slice";
                # a hex-encoded "slice" entry is rejected.
                "stack": [
                    ["tvm.Slice", boc]
                ]
            }

            response = requests.post(
                f"{TONCENTER_API_BASE}/runGetMethod",
                json=data,
                headers=headers,
                timeout=20,
            )
            response.raise_for_status()

            result = response.json().get('result')
            if not result or result.get('exit_code') != 0:
                return None

            # Result stack: [["cell", {"bytes": "..."}]]
            wallet_address_boc = b64decode(result['stack'][0][1]['bytes'])
            wallet_address_cell = Cell.one_from_boc(wallet_address_boc)
            wallet_address = wallet_address_cell.begin_parse().read_msg_addr()
            
            return wallet_address.to_string(
                is_user_friendly=True, is_url_safe=True, is_bounceable=True
            )

        except Exception as e:
            # It's good practice to log the exception
            print(f"Could not get wallet address: {e}")
            return None
