#! /usr/bin/env python3

"""Реализация клиента для управления контроллером шагового двигателя SMSD-LAN."""

import logging
from socket import AF_INET, SOCK_STREAM, socket
from typing import Callable

from serial import Serial

from .smsd import Smsd, SmsdError

_logger = logging.getLogger(__name__)
_logger.addHandler(logging.NullHandler())


def log(func: Callable) -> Callable:
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
        """Инициализация класса клиента с указанными параметрами."""

        self.socket = Serial(port=address, baudrate=115200, timeout=timeout)
        super().__init__()

    def __del__(self) -> None:
        """Закрытие соединения с устройством при удалении объекта."""

        if self.socket.is_open:
            self.socket.close()

    @log
    def _bus_exchange(self, packet: bytes) -> bytes:
        """Обмен по интерфейсу."""

        self.socket.reset_input_buffer()
        self.socket.reset_output_buffer()

        packet = self._escape(packet)

        self.socket.write(packet)
        answer = self.socket.read_until(b"\xFB")

        if not answer or answer[0] != ord(b"\xFA") or answer[-1] != ord(b"\xFB"):
            msg = "Invalid message format"
            raise SmsdError(msg)

        return self._unescape(answer)

    @staticmethod
    def _escape(packet: bytes) -> bytes:
        """Замена специальных символов внутри пакета парой байтов."""

        packet = packet.replace(b"\xFA", b"\xFE\x7A").\
                        replace(b"\xFB", b"\xFE\x7B").\
                        replace(b"\xFE", b"\xFE\x7E")
        return b"\xFA" + packet + b"\xFB"

    @staticmethod
    def _unescape(packet: bytes) -> bytes:
        """Обратная замена пары байтов внутри пакета на символы."""

        packet = packet[1:-1]
        return packet.replace(b"\xFE\x7A", b"\xFA").\
                      replace(b"\xFE\x7B", b"\xFB").\
                      replace(b"\xFE\x7E", b"\xFE")


class SmsdTcpClient(Smsd):
    """Класс клиента для управления SMSD-LAN по протоколу TCP."""

    def __init__(self, address: str, timeout: float = 1.0) -> None:
        """Инициализация класса клиента с указанными параметрами."""

        ip, tcp_port = address.split(":")
        self.socket = socket(AF_INET, SOCK_STREAM)
        self.socket.settimeout(timeout)
        self.socket.connect((ip, int(tcp_port)))

        super().__init__()

    def __del__(self) -> None:
        """Закрытие соединения с устройством при удалении объекта."""

        if self.socket:
            self.socket.close()

    @log
    def _bus_exchange(self, packet: bytes) -> bytes:
        """Обмен по интерфейсу."""

        self.socket.sendall(packet)
        return self.socket.recv(2048)


__all__ = ["SmsdTcpClient", "SmsdUsbClient"]
