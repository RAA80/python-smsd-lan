#! /usr/bin/env python3

"""Реализация клиента для управления контроллером шагового двигателя SMSD-LAN."""

from __future__ import annotations

import logging
from socket import AF_INET, SOCK_STREAM, socket
from typing import TYPE_CHECKING, Callable

from pymodbus.client import ModbusTcpClient
from serial import Serial

from smsd.exception import SmsdError
from smsd.modbus import Modbus
from smsd.smsd import Smsd

if TYPE_CHECKING:
    from pymodbus.pdu import ModbusPDU

_logger = logging.getLogger(__name__)
_logger.addHandler(logging.NullHandler())


def log(func: Callable[..., bytes]) -> Callable[..., bytes]:    # type: ignore
    """Вывод отладочной информации."""

    def wrapper(self: Callable[[bytes], bytes], packet: bytes) -> bytes:
        _logger.debug("Send frame: %r", list(packet))
        answer = func(self, packet)
        _logger.debug("Recv frame: %r", list(answer))
        return bytes(answer)

    return wrapper


class SmsdUsbClient(Smsd):
    """Класс клиента для управления SMSD-LAN через USB."""

    def __init__(self, address: str, timeout: float = 1.0) -> None:
        """Инициализация класса клиента для управления SMSD-LAN через USB."""

        self._socket = Serial(port=address, baudrate=115200, timeout=timeout)
        super().__init__()

    def __del__(self) -> None:
        """Закрытие соединения с устройством при удалении объекта."""

        if hasattr(self, "_socket"):
            self._socket.close()

    @log
    def _bus_exchange(self, packet: bytes) -> bytes:
        """Обмен по интерфейсу."""

        self._socket.reset_input_buffer()
        self._socket.reset_output_buffer()

        packet = self._escape(packet)

        self._socket.write(packet)
        answer = self._socket.read_until(b"\xFB")

        if not answer or answer[0] != ord(b"\xFA") or answer[-1] != ord(b"\xFB"):
            msg = "Invalid message format"
            raise SmsdError(msg)

        return self._unescape(answer)

    @staticmethod
    def _escape(packet: bytes) -> bytes:
        """Замена специальных символов внутри пакета парой байтов."""

        packet = packet.replace(b"\xFA", b"\xFE\x7A")\
                       .replace(b"\xFB", b"\xFE\x7B")\
                       .replace(b"\xFE", b"\xFE\x7E")
        return b"\xFA" + packet + b"\xFB"

    @staticmethod
    def _unescape(packet: bytes) -> bytes:
        """Обратная замена пары байтов внутри пакета на символы."""

        packet = packet[1:-1]
        return packet.replace(b"\xFE\x7A", b"\xFA")\
                     .replace(b"\xFE\x7B", b"\xFB")\
                     .replace(b"\xFE\x7E", b"\xFE")


class SmsdTcpClient(Smsd):
    """Класс клиента для управления SMSD-LAN по протоколу TCP."""

    def __init__(self, address: str, timeout: float = 1.0) -> None:
        """Инициализация класса клиента для управления SMSD-LAN по протоколу TCP."""

        ip, tcp_port = address.split(":")
        self._socket = socket(AF_INET, SOCK_STREAM)
        self._socket.settimeout(timeout)
        self._socket.connect((ip, int(tcp_port)))

        super().__init__()

    def __del__(self) -> None:
        """Закрытие соединения с устройством при удалении объекта."""

        if hasattr(self, "_socket"):
            self._socket.close()

    @log
    def _bus_exchange(self, packet: bytes) -> bytes:
        """Обмен по интерфейсу."""

        self._socket.sendall(packet)
        return self._socket.recv(2048)


class SmsdModbusClient(Modbus):
    """Класс клиента для управления SMSD-LAN по протоколу Modbus-TCP."""

    def __init__(self, address: str, timeout: float = 1.0, unit: int = 1) -> None:
        """Инициализация класса клиента для управления SMSD-LAN по протоколу
        Modbus-TCP.
        """

        ip, tcp_port = address.split(":")
        self._socket = ModbusTcpClient(host=ip, port=int(tcp_port), timeout=timeout)
        self._socket.connect()

        self.unit = unit

        super().__init__()

    def __del__(self) -> None:
        """Закрытие соединения с устройством при удалении объекта."""

        if hasattr(self, "_socket"):
            self._socket.close()

    def _write_bit(self, address: int, values: list[bool]) -> ModbusPDU:
        """Запись в битовый регистр Modbus."""

        result = self._socket.write_coils(address=address,
                                          values=values,
                                          slave=self.unit)
        return self._check_error(result)

    def _write_hr(self, address: int, values: list[int]) -> ModbusPDU:
        """Запись в регистр Modbus."""

        result = self._socket.write_registers(address=address,
                                              values=values,
                                              slave=self.unit)
        return self._check_error(result)

    def _read_hr(self, address: int, count: int) -> ModbusPDU:
        """Запись в регистр Modbus."""

        result = self._socket.read_holding_registers(address=address,
                                                     count=count,
                                                     slave=self.unit)
        return self._check_error(result)

    def _read_di(self, address: int, count: int) -> ModbusPDU:
        """Чтение дискретных входов."""

        result = self._socket.read_discrete_inputs(address=address,
                                                   count=count,
                                                   slave=self.unit)
        return self._check_error(result)


__all__ = ["SmsdModbusClient", "SmsdTcpClient", "SmsdUsbClient"]
