# import getpass
import os

from django.conf import settings

# if not os.environ.get("GOOGLE_API_KEY"):
#   os.environ["GOOGLE_API_KEY"] = getpass.getpass("Enter API key for Google Gemini: ")

os.environ["GOOGLE_API_KEY"] = settings.GOOGLE_API_KEY

from langchain.chat_models import init_chat_model

model = init_chat_model("gemini-2.5-flash", model_provider="google_genai")

print(model.invoke("Hello, world!").content)
