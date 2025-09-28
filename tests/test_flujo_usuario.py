import pytest
from unittest.mock import AsyncMock, MagicMock
from main import sistema, recolectar_datos, manejar_imagen_comprobante

@pytest.mark.asyncio
async def test_flujo_completo_usuario_con_imagen():
    sistema.configurar_rango_inicial("00-99")
    sistema.numeros_disponibles["10"] = True
    sistema.usuarios = {}
    sistema.user_datos = {}
    sistema.esperando_dato = {}
    sistema.numeros_seleccionados = {}

    user_id = 123456789
    nombre = "José Cova"
    telefono = "0414-1234567"
    cedula = "V-12345678"
    file_id = "photo_file_id_123"

    # Simular update y context
    message_mock = AsyncMock()
    update = MagicMock()
    update.message = message_mock
    update.effective_user.id = user_id
    context = MagicMock()

    # Paso 1: nombre
    message_mock.text = nombre
    sistema.user_datos[user_id] = {}
    sistema.esperando_dato[user_id] = "nombre"
    await recolectar_datos(update, context)

    # Paso 2: teléfono
    message_mock.text = telefono
    sistema.esperando_dato[user_id] = "telefono"
    await recolectar_datos(update, context)

    # Paso 3: cédula
    message_mock.text = cedula
    sistema.esperando_dato[user_id] = "cedula"
    await recolectar_datos(update, context)

    # ✅ Paso intermedio: simular selección de número
    sistema.numeros_seleccionados[user_id] = ['10']

    # ✅ Nuevo paso: marcar que estamos esperando la imagen
    sistema.esperando_dato[user_id] = "imagen"

    # Paso 4: imagen del comprobante
    photo_mock = MagicMock()
    photo_mock.file_id = file_id
    message_mock.photo = [photo_mock]
    await manejar_imagen_comprobante(update, context)

    assert sistema.usuarios[user_id]["imagen_file_id"] == file_id
    message_mock.reply_text.assert_called()
