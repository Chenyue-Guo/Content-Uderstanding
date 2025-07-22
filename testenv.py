import streamlit as st
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))
from backend.content_understanding_face_client import AzureContentUnderstandingFaceClient
from backend.content_understanding_client import AzureContentUnderstandingClient
import base64
import tempfile
from PIL import Image
import io

from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, get_bearer_token_provider



load_dotenv()
# ========== CONFIG ==========
# 请根据实际情况填写
ENDPOINT = os.getenv("AZURE_AI_ENDPOINT")
API_VERSION = os.getenv("AZURE_AI_API_VERSION")
SUBSCRIPTION_KEY = os.getenv("AZURE_SUBSCRIPTION_KEY")

credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")

face_client = AzureContentUnderstandingFaceClient(
    endpoint=ENDPOINT,
    api_version=API_VERSION,
    token_provider=token_provider
)
# content_client = AzureContentUnderstandingClient(
#     endpoint=ENDPOINT,
#     api_version=API_VERSION,
#     token_provider=token_provider
# )