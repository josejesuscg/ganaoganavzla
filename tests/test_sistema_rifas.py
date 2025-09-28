import pytest
from main import SistemaRifas

@pytest.fixture
def sistema():
    return SistemaRifas()

def test_configuracion_rango(sistema):
    sistema.configurar_rango_inicial("00-99")
    assert sistema.min_num == 0
    assert sistema.max_num == 99
    assert sistema.digitos == 2

def test_numero_valido(sistema):
    sistema.configurar_rango_inicial("000-999")
    assert sistema.numero_valido("123")
    assert not sistema.numero_valido("1000")
    assert not sistema.numero_valido("abc")

def test_parsear_rango_invalido(sistema):
    with pytest.raises(ValueError):
        sistema.configurar_rango_inicial("01-99")
