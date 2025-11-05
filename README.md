# BaleVibe — README & API Reference

A compact, friendly Python client for the Bale `tapi.bale.ai` bot API.
This document explains how to install, use and extend the `BaleBot` client (the `client.py` class you already have), with quick examples and a complete method reference for each public method in the class.

> Replace `YOUR_BOT_TOKEN` and `CHAT_ID` with real values when testing.

---

## Table of contents

* [Quick start](#quick-start)
* [Installing](#installing)
* [Design & behaviour notes](#design--behaviour-notes)
* [Examples](#examples)

  * [Simple sendMessage](#simple-sendmessage)
  * [Polling loop example (getUpdates)](#polling-loop-example-getupdates)
  * [Answering a callback query with `show_alert`](#answering-a-callback-query-with-show_alert)
  * [sendPoll (single-question, 2 answers)](#sendpoll-single-question-2-answers)
  * [Download a file (getFile + download_file)](#download-a-file-getfile--download_file)
  * [Set webhook (with certificate)](#set-webhook-with-certificate)
* [API Reference — `BaleBot` class](#api-reference---balebot-class)

  * [Construction & helpers](#construction--helpers)
  * [Polling / updates](#polling--updates)
  * [Message sending methods (send*)](#message-sending-methods-send)
  * [Chat management & admin](#chat-management--admin)
  * [Message editing & reply markup](#message-editing--reply-markup)
  * [Webhooks](#webhooks)
  * [File helpers](#file-helpers)
  * [Polls](#polls)
  * [Sticker helpers](#sticker-helpers)
  * [Payments / Invoices](#payments--invoices)
  * [Misc helpers](#misc-helpers)
* [Error handling & troubleshooting](#error-handling--troubleshooting)
* [Best practices & security notes](#best-practices--security-notes)
* [Tests / Contributing / License](#tests--contributing--license)

---

## Quick start

```python
from client import BaleBot    # or `from balevibe import BaleBot` if you packaged it

TOKEN = "YOUR_BOT_TOKEN"
CHAT_ID = 123456789

bot = BaleBot(TOKEN)
bot.sendMessage(chat_id=CHAT_ID, text="Hello from BaleVibe!")
```

---

## Installing

This client is a single-file class (no packaging required). Requirements:

* Python 3.8+
* `requests` library

Install requests:

```bash
pip install requests
```

Drop `client.py` into your project or import the `BaleBot` class from the `balevibe` package when you package it.

---

## Design & behaviour notes

* `BaleBot` is intentionally thin: it wraps Bale API endpoints via a small `_request` method that performs HTTP calls and returns the API `result` or raises a `RuntimeError` on failures.
* Many `send*` methods accept either:

  * a string (URL or file identifier), or
  * a path-like string (checked with `os.path.exists`), or
  * a file-like object (object with `.read()`), which will be uploaded via `multipart/form-data`.
* `answerCallbackQuery` supports `show_alert=True` (displays a modal alert to the user; see examples below).
* `getUpdates` is provided as a wrapper for polling; `setWebhook` / `deleteWebhook` / `getWebhookInfo` for webhook mode.
* File download helper: `getFile()` returns the File object; `download_file()` will download bytes when possible.

---

## Examples

### Simple `sendMessage`

```python
from client import BaleBot
bot = BaleBot("YOUR_BOT_TOKEN")
bot.sendMessage(chat_id=123456789, text="Hello world")
```

### Polling loop example (`getUpdates`)

```python
from client import BaleBot, time

bot = BaleBot("YOUR_BOT_TOKEN")
offset = 0
while True:
    updates = bot.getUpdates(offset=offset, timeout=30)
    if not updates:
        continue
    for upd in updates:
        offset = max(offset, upd.get("update_id", 0) + 1)
        if "message" in upd:
            msg = upd["message"]
            text = msg.get("text", "")
            chat_id = msg["chat"]["id"]
            if text == "/hello":
                bot.sendMessage(chat_id=chat_id, text="Hi!")
```

### Answering a callback query with `show_alert`

```python
# when you receive a callback query update:
cb = callback_query  # the callback_query dict from updates
bot.answerCallbackQuery(callback_query_id=cb["id"], text="Done!", show_alert=True)
```

### `sendPoll` (single question, two static answers)

```python
bot.sendPoll(
    chat_id=123456789,
    question="Which one do you prefer?",
    options=["Coffee", "Tea"]
)
```

### Download a file (getFile + `download_file`)

```python
file_id = "AgACAgU..."  # example file id you got in an update
file_info = bot.getFile(file_id)
data = bot.download_file(file_id)
if data:
    with open("downloaded.webm", "wb") as f:
        f.write(data)
```

### Set webhook (with certificate file-like)

```python
with open("cert.pem", "rb") as certificate_file:
    bot.setWebhook(url="https://example.com/your-webhook-path", certificate=certificate_file)
```

---

## API Reference — `BaleBot` class

> The entire client is a single class: `BaleBot`. Below is a grouped, method-by-method reference. Each entry includes signature, short description, arguments and a short example where helpful.

> **Note:** All methods return the `result` field from the Bale API JSON response on success, or raise `RuntimeError` on failure. The `_request` method enforces the JSON `ok` flag.

---

### Construction & helpers

#### `BaleBot(token: str, base_url: str = "https://tapi.bale.ai")`

Create a client instance.

* `token` — your bot token (string).
* `base_url` — base API URL; default `https://tapi.bale.ai`.

Usage:

```py
bot = BaleBot("MY_TOKEN")
```

#### `_request(method: str, http_method: str = "get", params: Optional[Dict]=None, data: Optional[Dict]=None, json: Optional[Dict]=None, files: Optional[Dict]=None) -> Any`

Internal helper to call API endpoints. You normally **do not** call this directly; use the public methods.

* Performs HTTP GET/POST, decodes JSON and returns `result`.
* Raises `RuntimeError` for HTTP, non-JSON, or API-level errors.

#### `getMe()`

Return basic information about the bot (equivalent to `getMe` on the Bale API).

Example:

```py
me = bot.getMe()
```

#### `ping() -> bool`

Call `getMe()` and return `True` if successful (catching exceptions).

Useful as a quick API-level health check.

#### `ping_raw(timeout: float = 5.0) -> bool`

A low-level HTTP check to the `base_url` (not authenticated). Returns `True` if base URL is reachable (HTTP 200–399). Useful for DNS/HTTP reachability checks.

---

### Polling / updates

#### `getUpdates(offset: Optional[int] = None, timeout: Optional[int] = None, limit: Optional[int] = None)`

Wrapper for `getUpdates`. Use this in a polling loop. Provide `offset` to avoid processing the same update twice. Example usage in [Polling loop example](#polling-loop-example-getupdates).

---

### Message sending methods (send*)

All `send*` methods accept a `chat_id` (where required) and additional kwargs forwarded to the API. Many `send*` methods accept either:

* A file-like object (object with `.read()`) — the client uses `files` in the POST, or
* A string (URL or file_id or local path).

If file-like, the method will upload via multipart HTTP.

#### `sendMessage(chat_id, text, **kwargs)`

Send a text message.

#### `sendPhoto(chat_id, photo, **kwargs)`

`photo` can be a file-like, an HTTP URL, a file_id, or a local path.

#### `sendAudio(chat_id, audio, **kwargs)`

Supports file-like and URL/file_id.

#### `sendDocument(chat_id, document, **kwargs)`

#### `sendVideo(chat_id, video, **kwargs)`

#### `sendAnimation(chat_id, animation, **kwargs)`

#### `sendVoice(chat_id, voice, **kwargs)`

#### `sendLocation(chat_id, latitude, longitude, **kwargs)`

#### `sendContact(chat_id, phone_number, first_name, **kwargs)`

#### `sendChatAction(chat_id, action)`

e.g. `action="typing"`.

#### `sendMediaGroup(chat_id, media, **kwargs)`

Send an album / media group. `media` should be a list in the format expected by Bale API.

---

### Message editing & reply markup

#### `editMessageText(chat_id=None, message_id=None, inline_message_id=None, text=None, **kwargs)`

Edit a message's text. Use `chat_id` + `message_id` or `inline_message_id` for inline messages.

#### `editMessageCaption(chat_id=None, message_id=None, inline_message_id=None, caption=None, **kwargs)`

#### `editMessageReplyMarkup(chat_id=None, message_id=None, inline_message_id=None, reply_markup=None)`

---

### Callback query / Inline keyboard helpers

#### `answerCallbackQuery(callback_query_id: str, text: Optional[str] = None, show_alert: Optional[bool] = None, **kwargs)`

Acknowledge a callback query (inline button press).

* `text` — optional short text shown to the user (toast or alert).
* `show_alert` — `True` to show a modal alert (alert dialog), `False` for a small toast.

Example:

```py
bot.answerCallbackQuery(callback_query_id="abc", text="Saved!", show_alert=False)
```

#### `answerWebAppQuery(web_app_query_id, result)`

Forward web app query responses.

---

### Webhooks

#### `setWebhook(url: str, certificate: Optional[IO] = None, max_connections: Optional[int] = None, allowed_updates: Optional[List[str]] = None, drop_pending_updates: Optional[bool] = None)`

Set a webhook. If `certificate` is a file-like object it will be uploaded as multipart/form-data.

#### `deleteWebhook(drop_pending_updates: Optional[bool] = None)`

Delete the webhook.

#### `getWebhookInfo()`

Return webhook information.

---

### File helpers

#### `getFile(file_id: str) -> Dict[str, Any]`

Return the File object (including `file_path` on success).

#### `file_download_url(file_obj_or_path: Union[Dict[str, Any], str]) -> Optional[str]`

Constructs the standard Bale download URL for a `file_path` or file object returned by `getFile`.

#### `download_file(file_id: str, timeout: int = 30) -> Optional[bytes]`

Convenience: `getFile()` + download the file bytes via the standard `tapi.bale.ai/file/bot<TOKEN>/<file_path>` URL. Returns bytes or `None` on failure.

**Important:** Some servers or deployments may return alternative fields (`file_url`, `file_bytes`). If your Bale server differs, you may need to adapt this helper.

---

### Polls

#### `sendPoll(chat_id, question: str, options: List[str], **kwargs)`

Send a poll. `options` is a list of strings (each option). Additional kwargs accepted by the Bale API are forwarded (e.g. `is_anonymous`, `allows_multiple_answers`, `type`, etc.)

Example:

```py
bot.sendPoll(chat_id=123, question="Coffee or Tea?", options=["Coffee", "Tea"])
```

#### `stopPoll(chat_id, message_id, **kwargs)`

Stop a running poll (requires `chat_id` and `message_id` of the poll message).

---

### Sticker helpers

#### `sendSticker(chat_id, sticker, **kwargs)`

Send a sticker. `sticker` can be file-like or file_id/URL.

#### `createNewStickerSet(user_id, name, title, **kwargs)`

#### `addStickerToSet(user_id, name, **kwargs)`

#### `deleteStickerFromSet(sticker)`

#### `uploadStickerFile(user_id, png_sticker_file)`

Upload a sticker file (PNG) for a user.

---

### Payments / Invoices

#### `sendInvoice(chat_id, title, description, payload_str, provider_token, start_parameter, currency, prices, **kwargs)`

#### `createInvoiceLink(title, description, payload_str, provider_token, currency, prices, **kwargs)`

#### `answerPreCheckoutQuery(pre_checkout_query_id, ok: bool, **kwargs)`

---

### Chat management & admin

#### `getChat(chat_id)`

#### `getChatMembersCount(chat_id)`

#### `getChatAdministrators(chat_id)`

#### `getChatMember(chat_id, user_id)`

#### `leaveChat(chat_id)`

#### `setChatTitle(chat_id, title)`

#### `setChatDescription(chat_id, description)`

#### `deleteChatPhoto(chat_id)`

#### `createChatInviteLink(chat_id, **kwargs)`

#### `revokeChatInviteLink(chat_id, invite_link)`

#### `exportChatInviteLink(chat_id)`

#### `banChatMember(chat_id, user_id, **kwargs)`

#### `unbanChatMember(chat_id, user_id)`

#### `restrictChatMember(chat_id, user_id, **kwargs)`

#### `promoteChatMember(chat_id, user_id, **kwargs)`

---

### Messages management

#### `deleteMessage(chat_id, message_id)`

#### `forwardMessage(chat_id, from_chat_id, message_id)`

#### `copyMessage(chat_id, from_chat_id, message_id, **kwargs)`

---

### Misc helpers

#### `sendMediaGroup(chat_id, media, **kwargs)`

#### `sendSticker(chat_id, sticker, **kwargs)`

#### `askReview(**kwargs)` — helper wrapper for app-specific reviews (if API provides it)

---

## Error handling & troubleshooting

* The client raises `RuntimeError` for:

  * network/HTTP exceptions when calling the API;
  * non-JSON responses; or
  * API responses with `ok: False` (the API `description` is included in the `RuntimeError`).
* If you see `API error getUpdates: Not Found` or similar:

  * check that `token` is correct and not expired;
  * verify your `base_url` (some deployments or staging environments use a custom URL);
  * confirm that the Bale API supports the exact method name you're calling.
* File uploads failing:

  * ensure file-like objects are opened in binary mode (`"rb"`) when passing to `sendDocument/sendPhoto/...`.
* If `download_file()` returns `None`, inspect `getFile()` response to determine if the API returns `file_path`, `file_url` or `file_bytes` and adapt the helper if needed.

---

## Best practices & security notes

* **Never** hardcode production tokens in repository code. Use environment variables in CI / runtime:

  ```python
  import os
  token = os.environ["BALEVIBE_TOKEN"]
  bot = BaleBot(token)
  ```
* Prefer streaming for very large files (the thin client currently downloads into memory with `requests.get(...).content`). For large files, implement a streaming download with `r.iter_content(chunk_size=...)`.
* Be cautious about storing user files long-term. Consider a TTL policy for temporary storage.
* Use `answerCallbackQuery(..., show_alert=True)` sparingly – modal alerts are interruptive to users.
* Use proper exception handling around bot operations in production (backoff + retries for flaky network).

---

## Tests / Contributing / License

* Add unit tests for:

  * `_request` error handling (mock HTTP responses),
  * file handling (file-like vs path vs URL),
  * `file_download_url` helper.
* For integration tests, run a small local mock server that mimics `getFile` and `getUpdates` responses rather than hitting production.
* Contributions: open PRs, follow repository style, add examples to `/examples` and test coverage.
* Suggested license: MIT (or whatever license you prefer). Add `LICENSE` file to repo.

---
