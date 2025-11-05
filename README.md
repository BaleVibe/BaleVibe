# BaleVibe

BaleVibe is a lightweight Python wrapper for the Bale messenger bot API (tapi.bale.ai).
This initial release includes support for the API methods marked as available (🟢) and new (🔵) from the user's spec.

## Quickstart

```py
from balevibe import BaleBot
bot = BaleBot("YOUR_TOKEN")
bot.sendMessage(chat_id=12345, text="Hello from BaleVibe")
```

## License
MIT
