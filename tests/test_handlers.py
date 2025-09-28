import pytest
from unittest.mock import MagicMock, AsyncMock
from main import start, sistema

@pytest.mark.asyncio
async def test_start_responde():
    update = MagicMock()
    update.message = AsyncMock()
    context = MagicMock()
    update.message.text = "/start"
    update.effective_user.id = "123456"
    update.callback_query = None
    sistema.activo = True

    await start(update, context)
    update.message.reply_text.assert_called_once()
