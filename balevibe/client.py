import requests
from typing import Optional, Any, Dict

class BaleBot:
    """Simple Bale bot client for tapi.bale.ai — supports 🟢 and 🔵 methods.

    Usage:
        bot = BaleBot("<TOKEN>")
        bot.sendMessage(chat_id, "hello")
    """
    def __init__(self, token: str, base_url: str = "https://tapi.bale.ai"):
        self.token = token
        if base_url.endswith("/"):
            base_url = base_url[:-1]
        self.api_url = f"{base_url}/bot{token}/"

    def _request(self, method: str, http_method: str = "get", params: Optional[Dict]=None, data: Optional[Dict]=None, json: Optional[Dict]=None, files: Optional[Dict]=None) -> Any:
        url = self.api_url + method
        try:
            if http_method.lower() == "get":
                r = requests.get(url, params=params, timeout=30)
            else:
                r = requests.post(url, params=params, data=data, json=json, files=files, timeout=60)
        except Exception as e:
            raise RuntimeError(f"HTTP error while calling {method}: {e!s}")
        try:
            result = r.json()
        except ValueError:
            raise RuntimeError(f"Non-JSON response from API ({r.status_code}): {r.text!s}")
        if not result.get("ok", False):
            raise RuntimeError(f"API error {method}: {result.get('description', 'no description')}")
        return result.get("result")

    # Basic / commonly used methods (🟢 and 🔵 only)
    def getMe(self):
        return self._request("getMe", "get")

    def sendMessage(self, chat_id, text, **kwargs):
        payload = {"chat_id": chat_id, "text": text}
        payload.update(kwargs)
        return self._request("sendMessage", "post", json=payload)

    def sendPhoto(self, chat_id, photo, **kwargs):
        # photo can be file-like, file path, or URL/file_id
        if hasattr(photo, "read"):
            files = {"photo": photo}
            data = {"chat_id": chat_id}
            data.update(kwargs)
            return self._request("sendPhoto", "post", data=data, files=files)
        if isinstance(photo, str) and (photo.startswith("http") or photo.isdigit() or os.path.exists(photo)):
            payload = {"chat_id": chat_id, "photo": photo}
            payload.update(kwargs)
            return self._request("sendPhoto", "post", json=payload)
        # fallback
        payload = {"chat_id": chat_id, "photo": photo}
        payload.update(kwargs)
        return self._request("sendPhoto", "post", json=payload)

    def sendAudio(self, chat_id, audio, **kwargs):
        if hasattr(audio, "read"):
            files = {"audio": audio}
            data = {"chat_id": chat_id}
            data.update(kwargs)
            return self._request("sendAudio", "post", data=data, files=files)
        payload = {"chat_id": chat_id, "audio": audio}
        payload.update(kwargs)
        return self._request("sendAudio", "post", json=payload)

    def sendDocument(self, chat_id, document, **kwargs):
        if hasattr(document, "read"):
            files = {"document": document}
            data = {"chat_id": chat_id}
            data.update(kwargs)
            return self._request("sendDocument", "post", data=data, files=files)
        payload = {"chat_id": chat_id, "document": document}
        payload.update(kwargs)
        return self._request("sendDocument", "post", json=payload)

    def sendVideo(self, chat_id, video, **kwargs):
        if hasattr(video, "read"):
            files = {"video": video}
            data = {"chat_id": chat_id}
            data.update(kwargs)
            return self._request("sendVideo", "post", data=data, files=files)
        payload = {"chat_id": chat_id, "video": video}
        payload.update(kwargs)
        return self._request("sendVideo", "post", json=payload)

    def sendAnimation(self, chat_id, animation, **kwargs):
        if hasattr(animation, "read"):
            files = {"animation": animation}
            data = {"chat_id": chat_id}
            data.update(kwargs)
            return self._request("sendAnimation", "post", data=data, files=files)
        payload = {"chat_id": chat_id, "animation": animation}
        payload.update(kwargs)
        return self._request("sendAnimation", "post", json=payload)

    def sendVoice(self, chat_id, voice, **kwargs):
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

    def answerCallbackQuery(self, callback_query_id, **kwargs):
        payload = {"callback_query_id": callback_query_id}
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

    def sendSticker(self, chat_id, sticker, **kwargs):
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
