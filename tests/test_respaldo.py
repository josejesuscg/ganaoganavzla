import pytest
from unittest.mock import patch, MagicMock

@patch("respaldo._obtener_hoja")
def test_respaldo_ticket(mock_hoja):
    hoja = MagicMock()
    mock_hoja.return_value = hoja
    from respaldo import respaldar_ticket
    r = respaldar_ticket("T1", "Jose", 1, "0412", "V123", ["01", "02"])
    assert r is True
    hoja.insert_row.assert_called_once()

@patch("respaldo._obtener_hoja")
def test_actualizar_estado_ticket(mock_hoja):
    hoja = MagicMock()
    hoja.findall.return_value = [MagicMock(row=2)]
    mock_hoja.return_value = hoja
    from respaldo import actualizar_estado_ticket
    r = actualizar_estado_ticket("T1", "Verificado")
    assert r is True
    hoja.update_cell.assert_called_once_with(2, 9, "Verificado")
