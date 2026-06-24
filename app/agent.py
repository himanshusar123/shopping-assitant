# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import os
import threading
from functools import cached_property

import google.auth
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.genai import Client, types

from app.app_utils.catalog import get_by_id, search_catalog

load_dotenv()

_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"


# Setup logger for security auditing
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("secure_shopping_assistant")


class MockKeyGemini(Gemini):
    @property
    def api_key(self) -> str:
        return os.getenv("GEMINI_API_KEY", "")

    @cached_property
    def api_client(self) -> Client:
        from google.genai import Client

        if os.getenv("GOOGLE_GENAI_USE_VERTEXAI") == "True":
            return Client()
        return Client(api_key=self.api_key)

    @cached_property
    def _live_api_client(self) -> Client:
        from google.genai import Client

        if os.getenv("GOOGLE_GENAI_USE_VERTEXAI") == "True":
            return Client()
        return Client(api_key=self.api_key)



# Thread-safety lock to prevent race conditions during redemption checks (Tampering Mitigation)
lock = threading.Lock()

# Simulated database of registered users
REGISTERED_USERS = {"user123", "buyer456", "customer789", "student_user"}

# Simulated secret credentials map for user authentication
USER_CREDENTIALS = {
    "user123": "token123",
    "buyer456": "token456",
    "customer789": "token789",
    "student_user": "student_pass",
}

# In-memory store for single-use discount codes
DISCOUNT_CODES = {
    "WELCOME50": {"discount": "50% off", "redeemed_by": None},
    "SUMMER20": {"discount": "20% off", "redeemed_by": None},
}


def login(user_id: str, secret_token: str, tool_context: ToolContext) -> dict:
    """Authenticates the user's session with their credentials.

    Args:
        user_id: The registered ID of the user.
        secret_token: The user's secret password or credential token.

    Returns:
        A status dictionary indicating success or failure.
    """
    try:
        if not user_id or not secret_token:
            return {"status": "error", "message": "Missing user_id or secret_token."}

        uid = user_id.strip()
        token = secret_token.strip()

        if uid not in REGISTERED_USERS:
            logger.warning(
                f"Audit log: Failed authentication attempt for unregistered ID '{uid}'."
            )
            return {"status": "error", "message": "Invalid credentials."}

        if USER_CREDENTIALS.get(uid) == token:
            tool_context.state["authenticated_user_id"] = uid
            tool_context.state["failed_attempts"] = 0
            logger.info(f"Audit log: User '{uid}' successfully authenticated.")
            return {
                "status": "success",
                "message": f"Successfully authenticated user '{uid}'.",
            }

        logger.warning(
            f"Audit log: Failed authentication attempt (incorrect credentials) for user '{uid}'."
        )
        return {"status": "error", "message": "Invalid credentials."}

    except Exception as e:
        logger.error(f"Error in login: {e}")
        return {
            "status": "error",
            "message": "An internal error occurred during authentication.",
        }


def redeem_discount_code(code: str, tool_context: ToolContext) -> dict:
    """Redeems a single-use discount code for the currently authenticated user session.

    Args:
        code: The discount code to redeem (e.g. WELCOME50, SUMMER20).

    Returns:
        A dictionary containing the status of the redemption, the discount value, or error details.
    """
    try:
        # 1. Identity Spoofing & Privilege Elevation Mitigation
        user_id = tool_context.state.get("authenticated_user_id")
        if not user_id:
            logger.warning(
                "Audit log: Unauthorized attempt to redeem coupon code without active login."
            )
            return {
                "status": "error",
                "message": "You must login first using your registered User ID and credentials before redeeming discount codes.",
            }

        # 2. Denial of Service (DoS) / Brute-Force Mitigation
        failed_count = tool_context.state.get("failed_attempts", 0)
        if failed_count >= 3:
            logger.warning(
                f"Audit log: Lockout active for user '{user_id}' due to too many invalid coupon attempts."
            )
            return {
                "status": "error",
                "message": "This session has been locked for coupon redemption due to excessive invalid attempts. Please contact support.",
            }

        code_upper = code.upper().strip()

        # 3. Tampering Mitigation (Lock guarding modifications)
        with lock:
            if code_upper not in DISCOUNT_CODES:
                failed_count += 1
                tool_context.state["failed_attempts"] = failed_count
                logger.warning(
                    f"Audit log: User '{user_id}' entered invalid coupon code '{code}'. Fail count: {failed_count}."
                )
                return {
                    "status": "error",
                    "message": f"Discount code '{code}' is not valid.",
                }

            code_info = DISCOUNT_CODES[code_upper]
            if code_info["redeemed_by"] is not None:
                failed_count += 1
                tool_context.state["failed_attempts"] = failed_count
                logger.warning(
                    f"Audit log: User '{user_id}' attempted to redeem already-redeemed code '{code_upper}'."
                )
                return {
                    "status": "error",
                    "message": f"Discount code '{code_upper}' has already been redeemed.",
                }

            # Redeem the code
            code_info["redeemed_by"] = user_id
            logger.info(
                f"Audit log: User '{user_id}' successfully redeemed discount code '{code_upper}' for {code_info['discount']}."
            )
            return {
                "status": "success",
                "message": f"Discount code '{code_upper}' successfully redeemed for user '{user_id}'!",
                "discount": code_info["discount"],
            }

    except Exception as e:
        logger.error(f"Error in redeem_discount_code: {e}")
        # Information Disclosure Mitigation (never leak stack trace to LLM/user)
        return {
            "status": "error",
            "message": "An internal error occurred during coupon redemption.",
        }


def search_products(query: str = "", category: str | None = None) -> dict:
    """Searches the product catalog by keyword and/or category.

    Args:
        query: Optional text query to search product names or descriptions.
        category: Optional category filter (e.g. 'Clothing', 'Electronics', 'Books').

    Returns:
        A dictionary with 'status' and 'results' containing matching products.
    """
    try:
        results = search_catalog(query=query, category=category)
        return {"status": "success", "results": results}
    except Exception as e:
        logger.error(f"Error in search_products: {e}")
        return {
            "status": "error",
            "message": "An error occurred while searching the catalog.",
        }


def get_product_details(product_id: str) -> dict:
    """Gets the detailed specifications, price, and stock levels of a product by ID.

    Args:
        product_id: The unique ID of the product (e.g., 'E101', 'C201').

    Returns:
        A dictionary with 'status' and product details, or an error if not found.
    """
    try:
        product = get_by_id(product_id)
        if product:
            return {"status": "success", "product": product}
        return {
            "status": "error",
            "message": f"Product with ID '{product_id}' not found.",
        }
    except Exception as e:
        logger.error(f"Error in get_product_details: {e}")
        return {
            "status": "error",
            "message": "An error occurred while fetching product details.",
        }


def recommend_products(preferences: str) -> dict:
    """Recommends products based on user interests, categories, or price ranges.

    Args:
        preferences: A description of user preferences (e.g. 'looking for soft organic clothes' or 'tech under $100').

    Returns:
        A dictionary with 'status' and 'results' containing recommended products.
    """
    try:
        prefs = preferences.lower()
        results = []

        cats = []
        if (
            "tech" in prefs
            or "electronic" in prefs
            or "wireless" in prefs
            or "sound" in prefs
        ):
            cats.append("Electronics")
        if (
            "clothe" in prefs
            or "wear" in prefs
            or "hoodie" in prefs
            or "shoes" in prefs
            or "organic" in prefs
        ):
            cats.append("Clothing")
        if "book" in prefs or "read" in prefs or "art" in prefs or "agent" in prefs:
            cats.append("Books")

        max_price = float("inf")
        if "under $" in prefs:
            try:
                parts = prefs.split("under $")
                max_price = float(parts[1].split()[0])
            except Exception:
                pass
        elif "under" in prefs:
            try:
                parts = prefs.split("under")
                max_price = float(parts[1].split()[0])
            except Exception:
                pass

        from app.app_utils.catalog import PRODUCTS

        for prod in PRODUCTS:
            if cats and prod["category"] not in cats:
                continue
            if float(prod["price"]) > max_price:
                continue
            if not cats:
                keywords = prefs.split()
                matches = sum(
                    1
                    for kw in keywords
                    if kw in prod["name"].lower() or kw in prod["description"].lower()
                )
                if matches == 0:
                    continue
            results.append(prod)

        if not results:
            results = PRODUCTS[:3]

        return {"status": "success", "results": results}
    except Exception as e:
        logger.error(f"Error in recommend_products: {e}")
        return {
            "status": "error",
            "message": "An error occurred while building recommendations.",
        }


root_agent = Agent(
    name="shopping_assistant",
    model=MockKeyGemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are a secure, helpful AI shopping assistant for a retail store. Help customers browse items, "
        "search the product catalog, get product details, receive recommendations, and redeem discount codes.\n\n"
        "Security Rules for Sensitive Operations:\n"
        "1. To redeem a discount code, you MUST first verify that the user session is authenticated. Check if "
        "the user has logged in. If not, you MUST ask the user for their registered User ID and secret credential token, "
        "and call the `login` tool first.\n"
        "2. Only call the `redeem_discount_code` tool once the session is successfully authenticated.\n"
        "3. If a tool reports that the session is not authenticated, prompt the user to login and run `login`.\n"
        "4. If a user session is locked due to too many invalid attempts, inform them and ask them to contact support.\n\n"
        "Shopping Tools:\n"
        "- Use `search_products` to find items in the catalog.\n"
        "- Use `get_product_details` to retrieve specific product information by ID.\n"
        "- Use `recommend_products` to suggest products based on user interests or constraints."
    ),
    tools=[
        login,
        redeem_discount_code,
        search_products,
        get_product_details,
        recommend_products,
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
