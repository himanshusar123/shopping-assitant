# STRIDE Threat Model Assessment: Shopping Assistant Agent

This document presents a systematic threat modeling assessment of the **Shopping Assistant** agent architecture using the STRIDE methodology.

---

## 1. System Boundaries & Architecture Map

* **Entry Points**:
  * HTTP / JSON endpoints exposed via [app/fast_api_app.py](file:///C:/Users/Himanshu%20Sardana/secure-agent-lab/shopping-assistant/app/fast_api_app.py).
  * Command-line execution via `agents-cli run`.
  * Interactive CLI / Playground.
* **LLM Engine**:
  * [MockKeyGemini](file:///C:/Users/Himanshu%20Sardana/secure-agent-lab/shopping-assistant/app/agent.py#L30) (subclassing `Gemini` model) with simulated credentials (`AIzaSyD-mock-key-value-12345`).
* **Tool Layer**:
  * [redeem_discount_code](file:///C:/Users/Himanshu%20Sardana/secure-agent-lab/shopping-assistant/app/agent.py#L56) function.
* **Data Layer**:
  * In-memory Python dictionaries (`REGISTERED_USERS` set, `DISCOUNT_CODES` dictionary).

---

## 2. STRIDE Assessment

### 1. Spoofing (Identity Spoofing)
* **Finding**: The `redeem_discount_code` tool verifies the presence of `user_id` in `REGISTERED_USERS`, but it does not authenticate the caller.
* **Threat**: A user can claim to be `user123` or `buyer456` without authentication (e.g. password, tokens, sessions), and redeem discount codes on their behalf.
* **Severity**: **High**
* **Mitigation**: Authenticate users prior to model interaction (e.g., via OAuth 2.0 or JWT session validation) and pass a verified user context that the LLM cannot override or spoof.

### 2. Tampering (Data/State Manipulation)
* **Finding**: Coupon state and user validation reside in-memory (`DISCOUNT_CODES`).
* **Threat**:
  1. *State resets*: Restarting the service resets coupon redemptions.
  2. *Race conditions*: There is no locking mechanism around the shared `DISCOUNT_CODES` state. If concurrent threads validate and redeem a coupon at the same time, multiple users could potentially redeem the same single-use code.
* **Severity**: **Medium**
* **Mitigation**: Move coupon and user state to a transactional database (e.g., Cloud SQL or Spanner) with ACID compliance and row-level locks on coupon codes during redemption.

### 3. Repudiation (Audit / Log Evasion)
* **Finding**: Redemptions simply modify Python dictionary states. No transactional logs or audit trails are created.
* **Threat**: If a discount is wrongfully applied or a code is exhausted, there is no immutable audit trail to prove which user performed the transaction or when.
* **Severity**: **Medium**
* **Mitigation**: Implement structured audit logging (e.g., Cloud Logging) for all successful and failed coupon redemption transactions.

### 4. Information Disclosure (Sensitive Data Leakage)
* **Finding**:
  1. There is a mock API key (`AIzaSyD-mock-key-value-12345`) hardcoded in [app/agent.py](file:///C:/Users/Himanshu%20Sardana/secure-agent-lab/shopping-assistant/app/agent.py#L31). While currently simulated, hardcoding credentials in source code creates a risk of exposure if replaced with live keys.
  2. Unhandled errors in the custom tool could leak internal dictionaries or tracebacks back to the user.
* **Severity**: **High**
* **Mitigation**: Remove any hardcoded keys. Load API keys from environment variables or Google Cloud Secret Manager. Catch all unexpected exceptions in tools and return clean, user-friendly error messages.

### 5. Denial of Service (DoS)
* **Finding**:
  1. There is no rate limiting on coupon redemption requests or brute-forcing of coupon codes.
  2. No rate limiting or cost controls on the LLM backend.
* **Threat**: Attackers can flood the endpoint with invalid coupon codes to exhaust resources, or spam the agent to inflate LLM API usage costs.
* **Severity**: **Medium**
* **Mitigation**: Configure API rate limiting on the FastAPI endpoint and implement a cooldown/lockout mechanism for repeatedly entering invalid discount codes.

### 6. Elevation of Privilege
* **Finding**: The LLM acts as the interpreter for user commands and orchestrates the parameters sent to `redeem_discount_code`.
* **Threat**: A user can use prompt injection techniques to trick the model into overriding the registered user check, or execute the tool with unauthorized parameter inputs.
* **Severity**: **High**
* **Mitigation**: Enforce input schemas and execute secondary backend checks within the tool itself. The tool must never rely solely on the LLM to validate the caller's privileges.
