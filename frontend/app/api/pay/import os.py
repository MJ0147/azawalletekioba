import os
from gradient import Gradient

api_client = Gradient(
    access_token=os.environ.get("DIGITAdop_v1_0e7525594f8c24db15ddd7cc4684dd9fced0c9728a01cd40005ad17097be76aa
LOCEAN_ACCESS_TOKEN_KEY") # default
)

api_response = api_client.agents.list()
if api_response.agents:
    print(api_response.agents[0].name)