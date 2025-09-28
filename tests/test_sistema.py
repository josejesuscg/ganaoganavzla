import pytest
from unittest.mock import MagicMock, AsyncMock

# Importamos las unidades de tu código que queremos probar
# Asegúrate de que tu archivo se llame 'main.py' y esté en el directorio correcto
from main import (
    nombre_valido,
    SistemaRifas,
    start,
    requiere_activado # Importamos el decorador también
)

## ---------------------------------------------------
## 1. Prueba para una Función Pura (Validación)
## ---------------------------------------------------
# Esta es la prueba más sencilla. Le damos una entrada y verificamos la salida.

def test_nombre_valido_funciona_con_nombres_correctos():
    """Verifica que la función acepte nombres válidos."""
    assert nombre_valido("Juan Perez") == True
    assert nombre_valido("María de los Ángeles") == True

def test_nombre_valido_falla_con_numeros_o_simbolos():
    """Verifica que la función rechace nombres con caracteres inválidos."""
    assert nombre_valido("Juan123") == False
    assert nombre_valido("Ana@") == False
    assert nombre_valido("") == False


## ---------------------------------------------------
## 2. Prueba para la Lógica Principal (Clase SistemaRifas)
## ---------------------------------------------------
# Usamos un "fixture" de pytest para crear una instancia limpia de la clase para cada prueba.

@pytest.fixture
def sistema_rifas():
    """Crea una instancia fresca de SistemaRifas para cada función de prueba."""
    return SistemaRifas()

def test_configuracion_rango_inicial(sistema_rifas):
    """Verifica que el rango de números se configure correctamente."""
    sistema_rifas.configurar_rango_inicial("00-99")

    assert sistema_rifas.activo == True
    assert sistema_rifas.min_num == 0
    assert sistema_rifas.max_num == 99
    assert sistema_rifas.digitos == 2
    assert len(sistema_rifas.numeros_disponibles) == 100
    assert "50" in sistema_rifas.numeros_disponibles # Un número de ejemplo
    assert sistema_rifas.numeros_disponibles["50"] == True # Debe estar disponible

def test_seleccionar_y_liberar_numero(sistema_rifas):
    """Simula la selección de un número y verifica que su estado cambie."""
    sistema_rifas.configurar_rango_inicial("000-999")

    # El número '123' debería estar disponible al inicio
    assert sistema_rifas.numeros_disponibles["123"] == True

    # Simulamos que un usuario lo selecciona (manualmente para la prueba)
    sistema_rifas.numeros_disponibles["123"] = False

    # Verificamos que ahora está ocupado
    assert sistema_rifas.numeros_disponibles["123"] == False

    # Simulamos que se libera
    sistema_rifas.numeros_disponibles["123"] = True

    # Verificamos que vuelve a estar disponible
    assert sistema_rifas.numeros_disponibles["123"] == True


## ---------------------------------------------------
## 3. Prueba para un Comando de Telegram (Handler)
## ---------------------------------------------------
# Esta es la parte más avanzada. No podemos probar a Telegram, así que "simulamos"
# los objetos `update` y `context` para ver si nuestra función `start` responde como debería.
# Usamos @pytest.mark.asyncio porque los handlers son funciones asíncronas.

@pytest.mark.asyncio
async def test_start_command():
    """Prueba que el comando /start responde con el mensaje de bienvenida."""

    # Importamos el sistema aquí para poder modificarlo
    from main import sistema

    # 1. Simular (mock) los objetos de Telegram
    update = MagicMock()
    update.message = AsyncMock() 
    context = MagicMock()

    # ---- LA CORRECCIÓN ESTÁ AQUÍ ----
    # a) Le decimos al mock QUÉ DEBE CONTENER el texto del mensaje.
    update.message.text = "/start"

    # b) El decorador también necesita un user_id, así que lo simulamos.
    update.effective_user.id = "123456"

    # c) Para que el decorador no falle, definimos callback_query como None.
    update.callback_query = None

    # d) Activamos el sistema para que el decorador @requiere_activado nos deje pasar.
    sistema.activo = True

    # 2. Llamar a nuestra función `start` con los objetos simulados
    await start(update, context)

    # 3. Verificar (assert) que nuestra función hizo lo que esperábamos.
    update.message.reply_text.assert_called_once()

    args, kwargs = update.message.reply_text.call_args
    assert "Bienvenido al Bot Oficial de Rifas" in args[0]
    assert kwargs['parse_mode'] == "Markdown"