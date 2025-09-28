import pytest
from main import nombre_valido, telefono_valido, cedula_valida, hash_valido

def test_nombre_valido():
    assert nombre_valido("Juan Perez")
    assert nombre_valido("María de los Ángeles")
    assert not nombre_valido("Juan123")
    assert not nombre_valido("Ana@")
    assert not nombre_valido("")

def test_telefono_valido():
    assert telefono_valido("+584141234567")
    assert telefono_valido("0412-1234567")
    assert not telefono_valido("123")

def test_cedula_valida():
    assert cedula_valida("V-12345678")
    assert cedula_valida("12345678")
    assert not cedula_valida("A" * 30)

def test_hash_valido():
    assert hash_valido("abc12345")
    assert not hash_valido("!!!@@@###")
