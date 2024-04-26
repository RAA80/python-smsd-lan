#! /usr/bin/env python3

"""Реализация клиента для управления контроллером шагового двигателя SMSD-LAN."""

import logging
from socket import AF_INET, SOCK_STREAM, socket

from serial import Serial

from .smsd import Smsd, SmsdError

_logger = logging.getLogger(__name__)
_logger.addHandler(logging.NullHandler())


def log(func):
    """Вывод отладочной информации."""

    def wrapper(self, packet):
        _logger.debug("Send frame: %r", list(packet))
        answer = func(self, packet)
        _logger.debug("Recv frame: %r", list(answer))
        return answer
    return wrapper


class BaseClient(Smsd):
    """Базовый класс клиента."""

    def __init__(self, address, **kwargs):
        """Инициализация класса клиента с указанным адресом."""

        super().__init__()

        self.socket = None
        self.address = address

        self.port = kwargs.get("port", 5000)
        self.timeout = kwargs.get("timeout", 1.0)

        self.connect()
        self.get_version()

    def __del__(self):
        """Закрытие соединения с устройством при удалении объекта."""

        if self.socket:
            self.socket.close()
        self.socket = None

    def connect(self):
        """Подключение к устройству."""

        raise NotImplementedError


class SmsdUsbClient(BaseClient):
    """Класс клиента для управления SMSD-LAN через USB."""

    def connect(self):
        """Подключение к устройству."""

        self.socket = Serial(port=self.address, baudrate=115200,
                             timeout=self.timeout)

    @log
    def _bus_exchange(self, packet):
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
    def _escape(packet):
        """Замена специальных символов внутри пакета парой байтов."""

        packet = packet.replace(b"\xFA", b"\xFE\x7A").\
                        replace(b"\xFB", b"\xFE\x7B").\
                        replace(b"\xFE", b"\xFE\x7E")
        return b"\xFA" + packet + b"\xFB"

    @staticmethod
    def _unescape(packet):
        """Обратная замена пары байтов внутри пакета на символы."""

        packet = packet[1:-1]
        return packet.replace(b"\xFE\x7A", b"\xFA").\
                      replace(b"\xFE\x7B", b"\xFB").\
                      replace(b"\xFE\x7E", b"\xFE")


class SmsdTcpClient(BaseClient):
    """Класс клиента для управления SMSD-LAN по протоколу TCP."""

    def connect(self):
        """Подключение к устройству."""

        self.server = (self.address, self.port)
        self.socket = socket(AF_INET, SOCK_STREAM)
        self.socket.settimeout(self.timeout)
        self.socket.connect(self.server)

    @log
    def _bus_exchange(self, packet):
        """Обмен по интерфейсу."""

        self.socket.sendall(packet)
        return self.socket.recv(2048)


__all__ = ["SmsdTcpClient", "SmsdUsbClient"]
