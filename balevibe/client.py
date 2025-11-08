# client.py
"""
BaleVibe client - enhanced single-file client with typed payloads, filters, middleware and flexible handlers.

Keep this file compatible with older code by using the same method names (sendMessage, getFile, ...).
New features:
 - dataclasses: User, Chat, Message, CallbackQuery, Poll, Update
 - composable Filter objects
 - decorators: @bot.on_message(filter=...), @bot.on_callback_query(), @bot.on_update()
 - middleware support
 - threaded and asyncio polling; handlers can be sync or async

Notes:
 - Polling starts automatically when BaleBot(...) is instantiated (background thread).
 - You can still call stop_polling()/start_polling() if you want to control it.
"""

from __future__ import annotations
import os
import re
import time
import json
import logging
import inspect
import threading
import asyncio
from dataclasses import dataclass, field
from typing import Optional, Any, Dict, List, Callable, Union, IO, Pattern, Tuple

import requests
from functools import partial

# ---- logging ----
logger = logging.getLogger("balevibe")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s balevibe: %(message)s"))
    logger.addHandler(h)
logger.setLevel(logging.INFO)

# ---- typed payloads ----
@dataclass
class User:
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    is_bot: Optional[bool] = False
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]):
        if not d:
            return None
        kw = {k: d.get(k) for k in ("id", "first_name", "last_name", "username", "is_bot")}
        extras = {k: v for k, v in d.items() if k not in kw}
        return cls(**kw, extra=extras)


@dataclass
class Chat:
    id: int
    type: Optional[str] = None
    title: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]):
        if not d:
            return None
        kw = {k: d.get(k) for k in ("id", "type", "title", "username", "first_name")}
        extras = {k: v for k, v in d.items() if k not in kw}
        return cls(**kw, extra=extras)


@dataclass
class Message:
    message_id: Optional[int]
    date: Optional[int]
    chat: Optional[Chat]
    from_user: Optional[User]
    text: Optional[str] = None
    caption: Optional[str] = None
    entities: Optional[List[Dict[str, Any]]] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]):
        if not d:
            return None
        msg_id = d.get("message_id") or d.get("id")
        chat = Chat.from_dict(d.get("chat", {}))
        user = User.from_dict(d.get("from") or d.get("sender") or {})
        kw = {
            "message_id": msg_id,
            "date": d.get("date"),
            "chat": chat,
            "from_user": user,
            "text": d.get("text"),
            "caption": d.get("caption"),
            "entities": d.get("entities"),
            "extra": {k: v for k, v in d.items() if k not in ("message_id","date","chat","from","text","caption","entities")},
            "raw": d,
        }
        return cls(**kw)


@dataclass
class CallbackQuery:
    id: str
    from_user: Optional[User]
    message: Optional[Message]
    chat_instance: Optional[str]
    data: Optional[str]
    extra: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]):
        if not d:
            return None
        user = User.from_dict(d.get("from") or {})
        message = Message.from_dict(d.get("message")) if d.get("message") else None
        kw = {
            "id": d.get("id"),
            "from_user": user,
            "message": message,
            "chat_instance": d.get("chat_instance"),
            "data": d.get("data"),
            "extra": {k: v for k, v in d.items() if k not in ("id","from","message","chat_instance","data")},
            "raw": d,
        }
        return cls(**kw)


@dataclass
class Poll:
    id: str
    question: str
    options: List[Dict[str, Any]]
    is_closed: bool
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]):
        if not d:
            return None
        kw = {
            "id": d.get("id"),
            "question": d.get("question"),
            "options": d.get("options", []),
            "is_closed": d.get("is_closed", False),
            "extra": {k: v for k, v in d.items() if k not in ("id","question","options","is_closed")}
        }
        return cls(**kw)


@dataclass
class Update:
    update_id: Optional[int]
    message: Optional[Message] = None
    edited_message: Optional[Message] = None
    channel_post: Optional[Message] = None
    edited_channel_post: Optional[Message] = None
    callback_query: Optional[CallbackQuery] = None
    inline_query: Optional[Dict[str, Any]] = None
    poll: Optional[Poll] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]):
        if not d:
            return None
        return cls(
            update_id=d.get("update_id"),
            message=Message.from_dict(d.get("message")) if "message" in d else None,
            edited_message=Message.from_dict(d.get("edited_message")) if "edited_message" in d else None,
            channel_post=Message.from_dict(d.get("channel_post")) if "channel_post" in d else None,
            edited_channel_post=Message.from_dict(d.get("edited_channel_post")) if "edited_channel_post" in d else None,
            callback_query=CallbackQuery.from_dict(d.get("callback_query")) if "callback_query" in d else None,
            inline_query=d.get("inline_query"),
            poll=Poll.from_dict(d.get("poll")) if "poll" in d else None,
            raw=d,
        )

# ---- Filter system ----
class Filter:
    """
    Composable filter object. Filters are callable fun(payload) -> bool.
    Combine with & (and), | (or), ~ (not).
    Use helpers: Filter.text(), Filter.command("start"), Filter.regex(r"^hello"), Filter.chat_type("group")
    """

    def __init__(self, func: Callable[[Any], bool], name: Optional[str] = None):
        self.func = func
        self.name = name or getattr(func, "__name__", "filter")

    def __call__(self, payload: Any) -> bool:
        try:
            return bool(self.func(payload))
        except Exception:
            logger.exception("Filter %s raised", self.name)
            return False

    def __and__(self, other: "Filter") -> "Filter":
        return Filter(lambda p: self(p) and other(p), name=f"({self.name} & {other.name})")

    def __or__(self, other: "Filter") -> "Filter":
        return Filter(lambda p: self(p) or other(p), name=f"({self.name} | {other.name})")

    def __invert__(self) -> "Filter":
        return Filter(lambda p: not self(p), name=f"(not {self.name})")

    @staticmethod
    def raw(fn: Callable[[Any], bool]) -> "Filter":
        return Filter(fn, name=getattr(fn, "__name__", "raw_filter"))

    @staticmethod
    def text(contains: Optional[str] = None) -> "Filter":
        if contains is None:
            return Filter(lambda p: bool(getattr(p, "text", None) or (isinstance(p, dict) and p.get("text"))), name="has_text")
        return Filter(lambda p: contains in (getattr(p, "text", None) or (isinstance(p, dict) and p.get("text") or "")), name=f"text_contains({contains})")

    @staticmethod
    def regex(pattern: Union[str, Pattern]) -> "Filter":
        if isinstance(pattern, str):
            pat = re.compile(pattern)
        else:
            pat = pattern
        return Filter(lambda p: bool(p and getattr(p, "text", None) and pat.search(p.text) or (isinstance(p, dict) and pat.search(p.get("text","")))), name=f"regex({pat.pattern})")

    @staticmethod
    def command(cmd: str) -> "Filter":
        cmd = cmd.lstrip("/")
        def _f(p):
            text = getattr(p, "text", None) or (isinstance(p, dict) and p.get("text"))
            if not text:
                return False
            # detect command at start
            parts = text.strip().split()
            if not parts:
                return False
            first = parts[0].lstrip("/")
            return first.split("@")[0].lower() == cmd.lower()
        return Filter(_f, name=f"command({cmd})")

    @staticmethod
    def chat_type(t: str) -> "Filter":
        return Filter(lambda p: (getattr(p, "chat", None).type if getattr(p, "chat", None) else (p.get("chat",{}).get("type") if isinstance(p, dict) else None)) == t,
                      name=f"chat_type({t})")

    @staticmethod
    def from_user(user_id: int) -> "Filter":
        return Filter(lambda p: (getattr(p, "from_user", None).id if getattr(p, "from_user", None) else (p.get("from",{}).get("id") if isinstance(p, dict) else None)) == user_id,
                      name=f"from_user({user_id})")

    @staticmethod
    def always_true() -> "Filter":
        return Filter(lambda p: True, name="always_true")

# ---- helper to detect handler signature and call safely ----
def _call_maybe_async(fn: Callable, *args, **kwargs):
    """Call handler that may be sync or async. Return coroutine if async otherwise run and return result."""
    if inspect.iscoroutinefunction(fn):
        return fn(*args, **kwargs)
    else:
        return fn(*args, **kwargs)

# ---- BaleBot class ----
class BaleBot:
    """Main BaleVibe client with dispatch, filters and middleware."""

    def __init__(self, token: str, base_url: str = "https://tapi.bale.ai", session: Optional[requests.Session] = None):
        self.token = token
        if base_url.endswith("/"):
            base_url = base_url[:-1]
        self.base_url = base_url
        self.api_url = f"{self.base_url}/bot{token}/"
        self._session = session or requests.Session()
        self._session.headers.update({"User-Agent": "balevibe/1.0"})
        # handlers: event_name -> list of (callable, Filter)
        self._handlers: Dict[str, List[Tuple[Callable, Filter]]] = {}
        # middleware: list of callables(bot, event_name, payload) -> payload_or_raise
        self._middleware: List[Callable[[Any, str, Any], Any]] = []
        # polling state
        self._polling = True
        self._poll_thread: Optional[threading.Thread] = None
        self._async_loop: Optional[asyncio.AbstractEventLoop] = None
        self._offset = 0
        # start polling automatically
        self._start_background_poll()

    # ----------------------------
    # low level request helper (keeps signature used previously)
    # ----------------------------
    def _request(self, method: str, http_method: str = "get", params: Optional[Dict] = None, data: Optional[Dict] = None, json: Optional[Dict] = None, files: Optional[Dict] = None) -> Any:
        url = self.api_url + method
        try:
            if http_method.lower() == "get":
                r = self._session.get(url, params=params, timeout=30)
            else:
                r = self._session.post(url, params=params, data=data, json=json, files=files, timeout=60)
        except Exception as e:
            logger.exception("HTTP error while calling %s", method)
            raise RuntimeError(f"HTTP error while calling {method}: {e!s}")
        try:
            result = r.json()
        except ValueError:
            logger.error("Non-JSON response from API (%s): %s", r.status_code, r.text)
            raise RuntimeError(f"Non-JSON response from API ({r.status_code}): {r.text!s}")
        if not result.get("ok", False):
            logger.error("API error %s: %s", method, result.get("description", "no description"))
            raise RuntimeError(f"API error {method}: {result.get('description', 'no description')}")
        return result.get("result")

    # ----------------------------
    # Keep legacy high-level API methods (sendMessage, sendVideo, ...). Many implemented for compatibility.
    # ----------------------------
    def getMe(self):
        return self._request("getMe", "get")

    def getUpdates(self, offset: Optional[int] = None, timeout: Optional[int] = None, limit: Optional[int] = None):
        params = {}
        if offset is not None:
            params["offset"] = offset
        if timeout is not None:
            params["timeout"] = timeout
        if limit is not None:
            params["limit"] = limit
        return self._request("getUpdates", "get", params=params)

    def ping(self) -> bool:
        try:
            _ = self.getMe()
            return True
        except Exception:
            return False

    def ping_raw(self, timeout: float = 5.0) -> bool:
        try:
            r = self._session.get(self.base_url, timeout=timeout)
            return 200 <= r.status_code < 400
        except Exception:
            return False

    def sendMessage(self, chat_id, text, **kwargs):
        payload = {"chat_id": chat_id, "text": text}
        payload.update(kwargs)
        return self._request("sendMessage", "post", json=payload)

    def sendPhoto(self, chat_id, photo: Union[str, IO], **kwargs):
        if hasattr(photo, "read"):
            files = {"photo": photo}
            data = {"chat_id": chat_id}
            data.update(kwargs)
            return self._request("sendPhoto", "post", data=data, files=files)
        payload = {"chat_id": chat_id, "photo": photo}
        payload.update(kwargs)
        return self._request("sendPhoto", "post", json=payload)

    def sendAudio(self, chat_id, audio: Union[str, IO], **kwargs):
        if hasattr(audio, "read"):
            files = {"audio": audio}
            data = {"chat_id": chat_id}
            data.update(kwargs)
            return self._request("sendAudio", "post", data=data, files=files)
        payload = {"chat_id": chat_id, "audio": audio}
        payload.update(kwargs)
        return self._request("sendAudio", "post", json=payload)

    def sendDocument(self, chat_id, document: Union[str, IO], **kwargs):
        if hasattr(document, "read"):
            files = {"document": document}
            data = {"chat_id": chat_id}
            data.update(kwargs)
            return self._request("sendDocument", "post", data=data, files=files)
        payload = {"chat_id": chat_id, "document": document}
        payload.update(kwargs)
        return self._request("sendDocument", "post", json=payload)

    def sendVideo(self, chat_id, video: Union[str, IO], **kwargs):
        if hasattr(video, "read"):
            files = {"video": video}
            data = {"chat_id": chat_id}
            data.update(kwargs)
            return self._request("sendVideo", "post", data=data, files=files)
        payload = {"chat_id": chat_id, "video": video}
        payload.update(kwargs)
        return self._request("sendVideo", "post", json=payload)

    def sendAnimation(self, chat_id, animation: Union[str, IO], **kwargs):
        if hasattr(animation, "read"):
            files = {"animation": animation}
            data = {"chat_id": chat_id}
            data.update(kwargs)
            return self._request("sendAnimation", "post", data=data, files=files)
        payload = {"chat_id": chat_id, "animation": animation}
        payload.update(kwargs)
        return self._request("sendAnimation", "post", json=payload)

    def sendVoice(self, chat_id, voice: Union[str, IO], **kwargs):
        if hasattr(voice, "read"):
            files = {"voice": voice}
            data = {"chat_id": chat_id}
            data.update(kwargs)
            return self._request("sendVoice", "post", data=data, files=files)
        payload = {"chat_id": chat_id, "voice": voice}
        payload.update(kwargs)
        return self._request("sendVoice", "post", json=payload)

    def sendLocation(self, chat_id, latitude, longitude, **kwargs):
        payload = {"chat_id": chat_id, "latitude": latitude, "longitude": longitude}
        payload.update(kwargs)
        return self._request("sendLocation", "post", json=payload)

    def sendContact(self, chat_id, phone_number, first_name, **kwargs):
        payload = {"chat_id": chat_id, "phone_number": phone_number, "first_name": first_name}
        payload.update(kwargs)
        return self._request("sendContact", "post", json=payload)

    def sendChatAction(self, chat_id, action):
        payload = {"chat_id": chat_id, "action": action}
        return self._request("sendChatAction", "post", json=payload)

    def sendInvoice(self, chat_id, title, description, payload_str, provider_token, start_parameter, currency, prices, **kwargs):
        payload = {
            "chat_id": chat_id,
            "title": title,
            "description": description,
            "payload": payload_str,
            "provider_token": provider_token,
            "start_parameter": start_parameter,
            "currency": currency,
            "prices": prices
        }
        payload.update(kwargs)
        return self._request("sendInvoice", "post", json=payload)

    def createInvoiceLink(self, title, description, payload_str, provider_token, currency, prices, **kwargs):
        payload = {
            "title": title,
            "description": description,
            "payload": payload_str,
            "provider_token": provider_token,
            "currency": currency,
            "prices": prices
        }
        payload.update(kwargs)
        return self._request("createInvoiceLink", "post", json=payload)

    def answerPreCheckoutQuery(self, pre_checkout_query_id, ok: bool, **kwargs):
        payload = {"pre_checkout_query_id": pre_checkout_query_id, "ok": ok}
        payload.update(kwargs)
        return self._request("answerPreCheckoutQuery", "post", json=payload)

    def answerCallbackQuery(self, callback_query_id: str, text: Optional[str] = None, show_alert: Optional[bool] = None, **kwargs):
        payload: Dict[str, Any] = {"callback_query_id": callback_query_id}
        if text is not None:
            payload["text"] = text
        if show_alert is not None:
            payload["show_alert"] = bool(show_alert)
        payload.update(kwargs)
        return self._request("answerCallbackQuery", "post", json=payload)

    def answerWebAppQuery(self, web_app_query_id, result):
        payload = {"web_app_query_id": web_app_query_id, "result": result}
        return self._request("answerWebAppQuery", "post", json=payload)

    def pinChatMessage(self, chat_id, message_id, **kwargs):
        payload = {"chat_id": chat_id, "message_id": message_id}
        payload.update(kwargs)
        return self._request("pinChatMessage", "post", json=payload)

    def unpinChatMessage(self, chat_id, message_id):
        payload = {"chat_id": chat_id, "message_id": message_id}
        return self._request("unpinChatMessage", "post", json=payload)

    def unpinAllChatMessages(self, chat_id):
        payload = {"chat_id": chat_id}
        return self._request("unpinAllChatMessages", "post", json=payload)

    def getChat(self, chat_id):
        payload = {"chat_id": chat_id}
        return self._request("getChat", "get", params=payload)

    def getChatMembersCount(self, chat_id):
        payload = {"chat_id": chat_id}
        return self._request("getChatMembersCount", "get", params=payload)

    def getChatAdministrators(self, chat_id):
        payload = {"chat_id": chat_id}
        return self._request("getChatAdministrators", "get", params=payload)

    def getChatMember(self, chat_id, user_id):
        payload = {"chat_id": chat_id, "user_id": user_id}
        return self._request("getChatMember", "get", params=payload)

    def leaveChat(self, chat_id):
        payload = {"chat_id": chat_id}
        return self._request("leaveChat", "post", json=payload)

    def setChatTitle(self, chat_id, title):
        payload = {"chat_id": chat_id, "title": title}
        return self._request("setChatTitle", "post", json=payload)

    def setChatDescription(self, chat_id, description):
        payload = {"chat_id": chat_id, "description": description}
        return self._request("setChatDescription", "post", json=payload)

    def deleteChatPhoto(self, chat_id):
        payload = {"chat_id": chat_id}
        return self._request("deleteChatPhoto", "post", json=payload)

    def createChatInviteLink(self, chat_id, **kwargs):
        payload = {"chat_id": chat_id}
        payload.update(kwargs)
        return self._request("createChatInviteLink", "post", json=payload)

    def revokeChatInviteLink(self, chat_id, invite_link):
        payload = {"chat_id": chat_id, "invite_link": invite_link}
        return self._request("revokeChatInviteLink", "post", json=payload)

    def exportChatInviteLink(self, chat_id):
        payload = {"chat_id": chat_id}
        return self._request("exportChatInviteLink", "post", json=payload)

    def banChatMember(self, chat_id, user_id, **kwargs):
        payload = {"chat_id": chat_id, "user_id": user_id}
        payload.update(kwargs)
        return self._request("banChatMember", "post", json=payload)

    def unbanChatMember(self, chat_id, user_id):
        payload = {"chat_id": chat_id, "user_id": user_id}
        return self._request("unbanChatMember", "post", json=payload)

    def restrictChatMember(self, chat_id, user_id, **kwargs):
        payload = {"chat_id": chat_id, "user_id": user_id}
        payload.update(kwargs)
        return self._request("restrictChatMember", "post", json=payload)

    def promoteChatMember(self, chat_id, user_id, **kwargs):
        payload = {"chat_id": chat_id, "user_id": user_id}
        payload.update(kwargs)
        return self._request("promoteChatMember", "post", json=payload)

    def deleteMessage(self, chat_id, message_id):
        payload = {"chat_id": chat_id, "message_id": message_id}
        return self._request("deleteMessage", "post", json=payload)

    def forwardMessage(self, chat_id, from_chat_id, message_id):
        payload = {"chat_id": chat_id, "from_chat_id": from_chat_id, "message_id": message_id}
        return self._request("forwardMessage", "post", json=payload)

    def copyMessage(self, chat_id, from_chat_id, message_id, **kwargs):
        payload = {"chat_id": chat_id, "from_chat_id": from_chat_id, "message_id": message_id}
        payload.update(kwargs)
        return self._request("copyMessage", "post", json=payload)

    def sendMediaGroup(self, chat_id, media, **kwargs):
        payload = {"chat_id": chat_id, "media": media}
        payload.update(kwargs)
        return self._request("sendMediaGroup", "post", json=payload)

    def sendSticker(self, chat_id, sticker: Union[str, IO], **kwargs):
        if hasattr(sticker, "read"):
            files = {"sticker": sticker}
            data = {"chat_id": chat_id}
            data.update(kwargs)
            return self._request("sendSticker", "post", data=data, files=files)
        payload = {"chat_id": chat_id, "sticker": sticker}
        payload.update(kwargs)
        return self._request("sendSticker", "post", json=payload)

    def createNewStickerSet(self, user_id, name, title, **kwargs):
        payload = {"user_id": user_id, "name": name, "title": title}
        payload.update(kwargs)
        return self._request("createNewStickerSet", "post", json=payload)

    def addStickerToSet(self, user_id, name, **kwargs):
        payload = {"user_id": user_id, "name": name}
        payload.update(kwargs)
        return self._request("addStickerToSet", "post", json=payload)

    def deleteStickerFromSet(self, sticker):
        payload = {"sticker": sticker}
        return self._request("deleteStickerFromSet", "post", json=payload)

    def uploadStickerFile(self, user_id, png_sticker_file):
        files = {"png_sticker": png_sticker_file}
        data = {"user_id": user_id}
        return self._request("uploadStickerFile", "post", data=data, files=files)

    def askReview(self, **kwargs):
        return self._request("askReview", "post", json=kwargs)

    def editMessageText(self, chat_id=None, message_id=None, inline_message_id=None, text=None, **kwargs):
        payload = {}
        if chat_id is not None and message_id is not None:
            payload["chat_id"] = chat_id
            payload["message_id"] = message_id
        if inline_message_id:
            payload["inline_message_id"] = inline_message_id
        if text is not None:
            payload["text"] = text
        payload.update(kwargs)
        return self._request("editMessageText", "post", json=payload)

    def editMessageCaption(self, chat_id=None, message_id=None, inline_message_id=None, caption=None, **kwargs):
        payload = {}
        if chat_id is not None and message_id is not None:
            payload["chat_id"] = chat_id
            payload["message_id"] = message_id
        if inline_message_id:
            payload["inline_message_id"] = inline_message_id
        if caption is not None:
            payload["caption"] = caption
        payload.update(kwargs)
        return self._request("editMessageCaption", "post", json=payload)

    def editMessageReplyMarkup(self, chat_id=None, message_id=None, inline_message_id=None, reply_markup=None):
        payload = {}
        if chat_id is not None and message_id is not None:
            payload["chat_id"] = chat_id
            payload["message_id"] = message_id
        if inline_message_id:
            payload["inline_message_id"] = inline_message_id
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return self._request("editMessageReplyMarkup", "post", json=payload)

    # ----------------------------
    # Webhook helpers
    # ----------------------------
    def setWebhook(self, url: str, certificate: Optional[IO] = None, max_connections: Optional[int] = None, allowed_updates: Optional[List[str]] = None, drop_pending_updates: Optional[bool] = None):
        """
        Set a webhook. If 'certificate' is file-like, it will be uploaded via multipart/form-data.
        """
        if certificate and hasattr(certificate, "read"):
            files = {"certificate": certificate}
            data = {"url": url}
            if max_connections is not None:
                data["max_connections"] = int(max_connections)
            if allowed_updates is not None:
                data["allowed_updates"] = allowed_updates
            if drop_pending_updates is not None:
                data["drop_pending_updates"] = bool(drop_pending_updates)
            return self._request("setWebhook", "post", data=data, files=files)
        payload = {"url": url}
        if max_connections is not None:
            payload["max_connections"] = int(max_connections)
        if allowed_updates is not None:
            payload["allowed_updates"] = allowed_updates
        if drop_pending_updates is not None:
            payload["drop_pending_updates"] = bool(drop_pending_updates)
        return self._request("setWebhook", "post", json=payload)

    def deleteWebhook(self, drop_pending_updates: Optional[bool] = None):
        payload: Dict[str, Any] = {}
        if drop_pending_updates is not None:
            payload["drop_pending_updates"] = bool(drop_pending_updates)
        return self._request("deleteWebhook", "post", json=payload)

    def getWebhookInfo(self):
        return self._request("getWebhookInfo", "get")

    # ----------------------------
    # File helpers (getFile + download convenience)
    # ----------------------------
    def getFile(self, file_id: str) -> Dict[str, Any]:
        """Return File object (dict) describing the file and file_path for download."""
        return self._request("getFile", "get", params={"file_id": file_id})

    def file_download_url(self, file_obj_or_path: Union[Dict[str, Any], str]) -> Optional[str]:
        """
        Given a File object returned by getFile (or a file_path string), return a download URL.
        - Bale provides: https://tapi.bale.ai/file/bot<TOKEN>/<file_path>
        """
        if isinstance(file_obj_or_path, str):
            file_path = file_obj_or_path
        else:
            file_path = file_obj_or_path.get("file_path") if isinstance(file_obj_or_path, dict) else None
        if not file_path:
            return None
        return f"{self.base_url}/file/bot{self.token}/{file_path}"

    def download_file(self, file_id: str, timeout: int = 30) -> Optional[bytes]:
        """
        Convenience: call getFile() then download bytes from the returned file_path URL.
        Returns bytes or None on failure.
        """
        file_info = self.getFile(file_id)
        if not file_info:
            return None
        url = self.file_download_url(file_info)
        if not url:
            return None
        try:
            r = self._session.get(url, timeout=timeout)
            if r.status_code == 200:
                return r.content
        except Exception:
            logger.exception("download_file failed")
        return None

    # ----------------------------
    # Poll helpers
    # ----------------------------
    def sendPoll(self, chat_id, question: str, options: List[str], **kwargs):
        payload = {"chat_id": chat_id, "question": question, "options": options}
        payload.update(kwargs)
        return self._request("sendPoll", "post", json=payload)

    def stopPoll(self, chat_id, message_id, **kwargs):
        payload = {"chat_id": chat_id, "message_id": message_id}
        payload.update(kwargs)
        return self._request("stopPoll", "post", json=payload)

    # ----------------------------
    # Misc helpers / admin
    # ----------------------------
    def getChatMembersCount(self, chat_id):
        payload = {"chat_id": chat_id}
        return self._request("getChatMembersCount", "get", params=payload)

    # ----------------------------
    # Handler registration API
    # ----------------------------
    def add_handler(self, event_name: str, fn: Callable, filter: Optional[Filter] = None):
        """Legacy-compatible: add a handler for an event_name (e.g. "message", "callback_query")"""
        if filter is None:
            filter = Filter.always_true()
        self._handlers.setdefault(event_name, []).append((fn, filter))
        logger.debug("Added handler %s for event %s (filter=%s)", getattr(fn, "__name__", repr(fn)), event_name, getattr(filter, "name", None))
        return fn

    def on(self, event_name: str, filter: Optional[Filter] = None):
        """Decorator: @bot.on('message', filter=Filter.command('start'))"""
        def deco(fn: Callable):
            return self.add_handler(event_name, fn, filter)
        return deco

    # convenience decorators (message, callback_query, update, edited_message, etc.)
    def on_message(self, filter: Optional[Filter] = None):
        return self.on("message", filter or Filter.always_true())

    def on_edited_message(self, filter: Optional[Filter] = None):
        return self.on("edited_message", filter or Filter.always_true())

    def on_callback_query(self, filter: Optional[Filter] = None):
        return self.on("callback_query", filter or Filter.always_true())

    def on_update(self, filter: Optional[Filter] = None):
        return self.on("update", filter or Filter.always_true())

    # middleware
    def add_middleware(self, fn: Callable[[ "BaleBot", str, Any], Any]):
        """Middleware called before handlers. Return modified payload or raise/return False to stop."""
        self._middleware.append(fn)
        return fn

    # ----------------------------
    # Dispatch helpers
    # ----------------------------
    def _run_middleware(self, event_name: str, payload: Any):
        """Run middleware chain. Middleware can modify payload; if any returns False/None -> stop dispatch."""
        for mw in self._middleware:
            try:
                res = mw(self, event_name, payload)
                # support async middleware if provided (not awaited here; user should provide sync mw for simplicity)
                if inspect.iscoroutine(res):
                    # schedule it (best-effort) and continue with original payload
                    try:
                        asyncio.get_event_loop().create_task(res)
                    except Exception:
                        pass
                else:
                    if res is False or res is None:
                        return None
                    # if middleware returns a mutated payload, use it
                    if res is not True:
                        payload = res
            except Exception:
                logger.exception("Middleware error for event %s", event_name)
                return None
        return payload

    def _dispatch_one(self, event_name: str, handler: Callable, filt: Filter, payload: Any):
        # evaluate filter before scheduling handler
        try:
            if not filt(payload):
                return
        except Exception:
            logger.exception("Filter evaluation failed for handler %s", getattr(handler, "__name__", repr(handler)))
            return
        # call sync or async handler adaptively:
        try:
            # handler may expect (bot, payload) or (payload)
            sig = inspect.signature(handler)
            params = len([p for p in sig.parameters.values() if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)])
            if inspect.iscoroutinefunction(handler):
                if params >= 2:
                    coro = handler(self, payload)
                else:
                    coro = handler(payload)
                # schedule the coroutine on running loop if present, otherwise run in a new loop in a thread
                try:
                    loop = asyncio.get_running_loop()
                    asyncio.create_task(coro)
                except RuntimeError:
                    # no running loop, run in a background thread loop
                    def _run_coro_in_thread(c):
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(c)
                        finally:
                            loop.close()
                    threading.Thread(target=_run_coro_in_thread, args=(coro,), daemon=True).start()
            else:
                # sync function: call with (bot, payload) or (payload)
                if params >= 2:
                    threading.Thread(target=lambda: handler(self, payload), daemon=True).start()
                else:
                    threading.Thread(target=lambda: handler(payload), daemon=True).start()
        except Exception:
            logger.exception("Handler invocation failed for event %s", event_name)

    def dispatch_update(self, raw_update: Dict[str, Any]):
        """
        Convert raw update dict -> Update dataclass, run middleware and dispatch to handlers.
        Also allow handlers registered to 'update' to receive the raw Update object or raw dict (depending on signature).
        """
        if not isinstance(raw_update, dict):
            return
        upd = Update.from_dict(raw_update)
        # run middleware
        for ev_name, payload in self._iter_update_events(upd, raw_update):
            # payload is dataclass or original dict depending
            # run middleware; if it returns None/False -> skip dispatch
            payload_after_mw = self._run_middleware(ev_name, payload)
            if payload_after_mw is None:
                continue
            # dispatch to 'update' handlers first (if any)
            if ev_name != "update":
                for (h, f) in self._handlers.get("update", []):
                    # pass entire raw update dict or Update object if handler expects dataclass
                    try:
                        # auto-select signature: if handler expects two args, send (bot, raw_update)
                        sig = inspect.signature(h)
                        params = len([p for p in sig.parameters.values() if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)])
                    except Exception:
                        params = 1
                    if params >= 2:
                        threading.Thread(target=lambda: h(self, raw_update), daemon=True).start()
                    else:
                        threading.Thread(target=lambda: h(raw_update), daemon=True).start()
            # then dispatch to specific event handlers
            for (h, f) in list(self._handlers.get(ev_name, [])):
                self._dispatch_one(ev_name, h, f, payload_after_mw)

    def _iter_update_events(self, upd: Update, raw_update: Dict[str, Any]) -> List[Tuple[str, Any]]:
        """
        Yield (event_name, payload) pairs for a given Update.
        Payload will be a dataclass wrapper (Message, CallbackQuery, Poll, etc.)
        """
        pairs = []
        # preserve order: message, edited_message, channel_post, edited_channel_post, callback_query, inline_query, poll
        if upd.message:
            pairs.append(("message", upd.message))
        if upd.edited_message:
            pairs.append(("edited_message", upd.edited_message))
        if upd.channel_post:
            pairs.append(("channel_post", upd.channel_post))
        if upd.edited_channel_post:
            pairs.append(("edited_channel_post", upd.edited_channel_post))
        if upd.callback_query:
            pairs.append(("callback_query", upd.callback_query))
        if upd.inline_query:
            pairs.append(("inline_query", upd.inline_query))
        if upd.poll:
            pairs.append(("poll", upd.poll))
        # always include raw update event as well
        pairs.append(("update", upd))
        return pairs

    # ----------------------------
    # Polling helpers
    # ----------------------------
    def _compute_allowed_updates(self) -> Optional[List[str]]:
        """
        Build allowed_updates list from registered handlers if possible to reduce payloads.
        If 'update' is registered return None (meaning 'all').
        """
        if "update" in self._handlers:
            return None
        mapping = {
            "message": "message",
            "edited_message": "edited_message",
            "channel_post": "channel_post",
            "edited_channel_post": "edited_channel_post",
            "callback_query": "callback_query",
            "inline_query": "inline_query",
            "poll": "poll"
        }
        allowed: List[str] = []
        for ev in self._handlers.keys():
            if ev in mapping:
                allowed.append(mapping[ev])
        return allowed or None

    def _get_updates(self, offset: int, timeout: int, allowed_updates: Optional[List[str]] = None):
        params = {"offset": offset, "timeout": timeout}
        if allowed_updates is not None:
            params["allowed_updates"] = json.dumps(allowed_updates)
        try:
            return self._request("getUpdates", "get", params=params) or []
        except Exception:
            logger.exception("getUpdates call failed")
            return []

    def _poll_loop(self):
        logger.info("Polling loop started (background)")
        timeout = 30
        while self._polling:
            allowed = self._compute_allowed_updates()
            updates = self._get_updates(self._offset, timeout, allowed_updates=allowed)
            if not updates:
                continue
            for u in updates:
                try:
                    self._offset = max(self._offset, u.get("update_id", 0) + 1)
                except Exception:
                    pass
                try:
                    self.dispatch_update(u)
                except Exception:
                    logger.exception("dispatch error")
        logger.info("Polling loop stopped")

    def _start_background_poll(self):
        if self._poll_thread and self._poll_thread.is_alive():
            return
        self._polling = True
        t = threading.Thread(target=self._poll_loop, daemon=True)
        t.start()
        self._poll_thread = t

    def start_polling(self, offset: int = 0, timeout: int = 30, allowed_updates: Optional[List[str]] = None):
        """Start polling in a background thread (explicit call)."""
        if self._polling and self._poll_thread and self._poll_thread.is_alive():
            logger.info("Polling already running")
            return
        self._offset = offset
        self._polling = True
        self._start_background_poll()

    def stop_polling(self):
        """Stop background polling."""
        self._polling = False
        if self._poll_thread and self._poll_thread.is_alive():
            try:
                self._poll_thread.join(timeout=1.0)
            except Exception:
                pass
        logger.info("Stopped polling")

    async def start_polling_async(self, offset: int = 0, timeout: int = 30, allowed_updates: Optional[List[str]] = None):
        """Async-friendly polling loop (awaitable)."""
        if self._async_loop:
            logger.warning("Async polling already running")
            return
        self._async_loop = asyncio.get_event_loop()
        self._offset = offset
        logger.info("Async polling started")
        try:
            while True:
                allowed = self._compute_allowed_updates()
                updates = await self._async_loop.run_in_executor(None, partial(self._get_updates, self._offset, timeout, allowed))
                if not updates:
                    continue
                for u in updates:
                    try:
                        self._offset = max(self._offset, u.get("update_id", 0) + 1)
                    except Exception:
                        pass
                    self.dispatch_update(u)
        finally:
            self._async_loop = None
            logger.info("Async polling stopped")

    # ----------------------------
    # utility / compatibility helpers
    # ----------------------------
    def event(self, name: str, filter: Optional[Filter] = None):
        """Alias for on(name) decorator"""
        return self.on(name, filter)

    def close(self):
        try:
            self.stop_polling()
        finally:
            try:
                self._session.close()
            except Exception:
                pass

# End of client.py
