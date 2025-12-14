#! /usr/bin/env python3

"""Реализация функций для работы с контроллером шагового двигателя SMSD-LAN."""

from __future__ import annotations

from ctypes import (POINTER, LittleEndianStructure, byref, c_ubyte, cast,
                    create_string_buffer, sizeof, string_at)
from itertools import cycle
from typing import TYPE_CHECKING, TypeVar

from smsd.protocol import (CODE_CMD, COMMANDS_RETURN_DATA_TYPE, LAN_COMMAND_TYPE,
                           LAN_ERROR_STATISTICS, MEMORY_BANK, MODE, POWERSTEP01,
                           POWERSTEP_STATUS_TYPEDEF, SMSD_CMD_TYPE,
                           SMSD_LAN_CONFIG_TYPE, STATUS, STATUS_IN_EVENT)

if TYPE_CHECKING:
    from _ctypes import _CData


class SmsdError(Exception):
    pass


T = TypeVar("T", bound=LittleEndianStructure)


class Smsd:
    """Класс функций для работы с контроллером шагового двигателя SMSD-LAN."""

    def __init__(self) -> None:
        """Инициализация класса Smsd."""

        self._version = self._get_version()
        self._cmd_id = cycle(range(256))

        self.status_powerstep01 = POWERSTEP_STATUS_TYPEDEF()

    def _bus_exchange(self, packet: bytes) -> bytes:
        """Обмен по интерфейсу."""

        raise NotImplementedError

    def _get_version(self) -> int:
        """Получение версии протокола."""

        if answer := self._bus_exchange(b""):
            return answer[1]

        msg = "Get protocol version error"
        raise SmsdError(msg)

    @staticmethod
    def _checksum(structure: LAN_COMMAND_TYPE) -> int:
        """Вычисление контрольной суммы (исключая поле 'xor')."""

        packet = string_at(byref(structure, 1), 5 + structure.LENGTH)
        return -sum(packet) & 0xFF

    def _make_request(self, command: CODE_CMD, buffer: bytes) -> bytes:
        """Формирование пакета для записи."""

        lan_cmd_type = LAN_COMMAND_TYPE()
        lan_cmd_type.VER = self._version
        lan_cmd_type.TYPE = command.value
        lan_cmd_type.ID = next(self._cmd_id)
        lan_cmd_type.LENGTH = len(buffer)
        lan_cmd_type.DATA = (c_ubyte * 1024)(*buffer)
        lan_cmd_type.XOR = self._checksum(lan_cmd_type)

        return string_at(byref(lan_cmd_type), 6 + lan_cmd_type.LENGTH)

    def _parse_answer(self, buffer: bytes) -> LAN_COMMAND_TYPE:
        """Расшифровка прочитанного пакета."""

        data = create_string_buffer(buffer)
        lan_cmd_type = cast(data, POINTER(LAN_COMMAND_TYPE)).contents

        if self._checksum(lan_cmd_type) != lan_cmd_type.XOR:
            msg = "Invalid message checksum"
            raise SmsdError(msg)

        return lan_cmd_type

    @staticmethod
    def _check_error(status: STATUS, structure: COMMANDS_RETURN_DATA_TYPE) -> bool:
        """Проверка возвращаемого значения на ошибку."""

        if status.value != structure.ERROR_OR_COMMAND:
            msg = STATUS(structure.ERROR_OR_COMMAND).name
            raise SmsdError(msg)

        return True

    def _execute(self, command: CODE_CMD, data: _CData, ret_type: type[T]) -> T:
        """Выполнение команды и получение ответа."""

        buffer = string_at(byref(data), sizeof(data))
        request = self._make_request(command, buffer)
        answer = self._bus_exchange(request)
        structure = self._parse_answer(answer)

        return cast(structure.DATA, POINTER(ret_type)).contents

    def _get_structure(self, command: CODE_CMD, structure: type[T]) -> T:
        """Посылка команды чтения структуры."""

        data = create_string_buffer(0)
        return self._execute(command, data, structure)

    def _set_structure(self, command: CODE_CMD, data: _CData, status: STATUS) -> bool:
        """Посылка команды записи структуры."""

        structure = self._execute(command, data, COMMANDS_RETURN_DATA_TYPE)
        return self._check_error(status, structure)

    def _powerstep01(self, command: POWERSTEP01, status: STATUS,
                           value: int) -> COMMANDS_RETURN_DATA_TYPE:
        """Посылка команды POWERSTEP01."""

        smsd_cmd_type = SMSD_CMD_TYPE()
        smsd_cmd_type.COMMAND = command.value
        smsd_cmd_type.DATA = value

        result = self._execute(CODE_CMD.POWERSTEP01, smsd_cmd_type,
                               COMMANDS_RETURN_DATA_TYPE)
        self.status_powerstep01 = result.STATUS_POWERSTEP01

        self._check_error(status, result)
        return result

    def _get_param(self, command: POWERSTEP01, status: STATUS) -> int:
        """Чтение значения параметра из устройства."""

        structure = self._powerstep01(command, status, 0)
        return int(structure.RETURN_DATA)

    def _set_param(self, command: POWERSTEP01, status: STATUS, value: int = 0) -> bool:
        """Запись нового значения параметра в устройство."""

        self._powerstep01(command, status, value)
        return True

    # Основные функции

    def authorization(self, password: str = "") -> bool:
        """Авторизация пользователя с помощью пароля. Если значение не задано, то
        используется пароль по умолчанию.
        """

        data = (c_ubyte * 8)(*bytearray(password, encoding="ascii")[:8]) \
               if password else \
               (c_ubyte * 8)(*(0xEF, 0xCD, 0xAB, 0x89, 0x67, 0x45, 0x23, 0x01))

        return self._set_structure(CODE_CMD.REQUEST, data, STATUS.OK_ACCESS)

    def set_password(self, password: str = "") -> bool:
        """Установка нового пароля авторизации. Если значение не задано, то
        устанавливается пароль по умолчанию.
        """

        data = (c_ubyte * 8)(*bytearray(password, encoding="ascii")[:8]) \
               if password else \
               (c_ubyte * 8)(*(0xEF, 0xCD, 0xAB, 0x89, 0x67, 0x45, 0x23, 0x01))

        return self._set_structure(CODE_CMD.PASSWORD_SET, data, STATUS.OK)

    def get_lan_config(self) -> SMSD_LAN_CONFIG_TYPE:
        """Чтение текущих сетевых настроек."""

        return self._get_structure(CODE_CMD.CONFIG_GET, SMSD_LAN_CONFIG_TYPE)

    def set_lan_config(self, config: SMSD_LAN_CONFIG_TYPE) -> bool:
        """Запись новых сетевых настроек."""

        return self._set_structure(CODE_CMD.CONFIG_SET, config, STATUS.OK)

    def get_error_statistics(self) -> LAN_ERROR_STATISTICS:
        """Чтение из памяти контроллера информации о количестве включений
        рабочего режима контроллера и статистики по ошибкам.
        """

        return self._get_structure(CODE_CMD.ERROR_GET, LAN_ERROR_STATISTICS)

    def get_max_speed(self) -> int:
        """Чтение текущего значения установленной максимальной скорости."""

        return self._get_param(POWERSTEP01.GET_MAX_SPEED, STATUS.GET_MAX_SPEED)

    def set_max_speed(self, speed: int) -> bool:
        """Установка максимальной скорости шагового двигателя."""

        return self._set_param(POWERSTEP01.SET_MAX_SPEED, STATUS.OK, speed)

    def get_min_speed(self) -> int:
        """Чтение текущего значения установленной минимальной скорости."""

        return self._get_param(POWERSTEP01.GET_MIN_SPEED, STATUS.GET_MIN_SPEED)

    def set_min_speed(self, speed: int) -> bool:
        """Установка минимальной скорости вращения двигателя."""

        return self._set_param(POWERSTEP01.SET_MIN_SPEED, STATUS.OK, speed)

    def get_speed(self) -> int:
        """Чтение текущего значения скорости."""

        return self._get_param(POWERSTEP01.GET_SPEED, STATUS.GET_SPEED)

    def run_f(self, speed: int) -> bool:
        """Старт непрерывного вращения двигателя в прямом направлении на
        указанной скорости.
        """

        return self._set_param(POWERSTEP01.RUN_F, STATUS.OK, speed)

    def run_r(self, speed: int) -> bool:
        """Старт непрерывного вращения двигателя в обратном направлении на
        указанной скорости.
        """

        return self._set_param(POWERSTEP01.RUN_R, STATUS.OK, speed)

    def get_mode(self) -> MODE:
        """Чтение настроек управления двигателем."""

        mode = MODE()
        mode.as_byte = self._get_param(POWERSTEP01.GET_MODE, STATUS.GET_MODE)
        return mode

    def set_mode(self, mode: MODE) -> bool:
        """Установка параметров управления двигателем."""

        return self._set_param(POWERSTEP01.SET_MODE, STATUS.OK, mode.as_byte)

    def set_acc(self, acceleration: int) -> bool:
        """Установка значения ускорения двигателя."""

        return self._set_param(POWERSTEP01.SET_ACC, STATUS.OK, acceleration)

    def set_dec(self, deceleration: int) -> bool:
        """Установка значения замедления шагового двигателя."""

        return self._set_param(POWERSTEP01.SET_DEC, STATUS.OK, deceleration)

    def move_f(self, steps: int) -> bool:
        """Перемещение двигателя в прямом направлении на указанную величину."""

        return self._set_param(POWERSTEP01.MOVE_F, STATUS.OK, steps)

    def move_r(self, steps: int) -> bool:
        """Перемещение двигателя в обратном направлении на указанную величину."""

        return self._set_param(POWERSTEP01.MOVE_R, STATUS.OK, steps)

    def get_abs_pos(self) -> int:
        """Чтение положения двигателя."""

        return self._get_param(POWERSTEP01.GET_ABS_POS, STATUS.GET_ABS_POS)

    def get_el_pos(self) -> int:
        """Чтение электрического положения ротора двигателя."""

        return self._get_param(POWERSTEP01.GET_EL_POS, STATUS.GET_EL_POS)

    def get_status_and_clr(self) -> int:
        """Чтение текущего статуса контроллера и сброса всех флагов ошибок."""

        return self._get_param(POWERSTEP01.GET_STATUS_AND_CLR, STATUS.OK)

    def get_status_in_event(self) -> STATUS_IN_EVENT:
        """Чтение текущего состояния входных сигналов."""

        status = STATUS_IN_EVENT()
        status.as_byte = self._get_param(POWERSTEP01.STATUS_IN_EVENT,
                                         STATUS.GET_STATUS_IN_EVENT)
        return status

    def go_to_f(self, position: int) -> bool:
        """Перемещение в заданную позицию в прямом направлении."""

        return self._set_param(POWERSTEP01.GO_TO_F, STATUS.OK, position)

    def go_to_r(self, position: int) -> bool:
        """Перемещение в заданную позицию в обратном направлении."""

        return self._set_param(POWERSTEP01.GO_TO_R, STATUS.OK, position)

    def set_mask_event(self, mask: int) -> bool:
        """Маскирование входных сигналов."""

        return self._set_param(POWERSTEP01.SET_MASK_EVENT, STATUS.OK, mask)

    def go_until_f(self, signal: int) -> bool:
        """Старт вращения двигателя в прямом направлении на максимальной
        скорости до получения сигнала на вход.
        """

        return self._set_param(POWERSTEP01.GO_UNTIL_F, STATUS.OK, signal)

    def go_until_r(self, signal: int) -> bool:
        """Старт вращения двигателя в обратном направлении на максимальной
        скорости до получения сигнала на вход.
        """

        return self._set_param(POWERSTEP01.GO_UNTIL_R, STATUS.OK, signal)

    def end(self) -> bool:
        """Обозначение конца программы."""

        return self._set_param(POWERSTEP01.END, STATUS.END_PROGRAMS)

    def scan_zero_f(self, speed: int) -> bool:
        """Поиск нулевого положения в прямом направлении с заданной скоростью."""

        return self._set_param(POWERSTEP01.SCAN_ZERO_F, STATUS.OK, speed)

    def scan_zero_r(self, speed: int) -> bool:
        """Поиск нулевого положения в обратном направлении с заданной скоростью."""

        return self._set_param(POWERSTEP01.SCAN_ZERO_R, STATUS.OK, speed)

    def scan_label_f(self, speed: int) -> bool:
        """Поиск метки положения в прямом направлении."""

        return self._set_param(POWERSTEP01.SCAN_LABEL_F, STATUS.OK, speed)

    def scan_label_r(self, speed: int) -> bool:
        """Поиск метки положения в обратном направлении."""

        return self._set_param(POWERSTEP01.SCAN_LABEL_R, STATUS.OK, speed)

    def go_zero(self) -> bool:
        """Перемещение в нулевое положение."""

        return self._set_param(POWERSTEP01.GO_ZERO, STATUS.OK)

    def go_label(self) -> bool:
        """Перемещение в положение, которое было отмечено как метка."""

        return self._set_param(POWERSTEP01.GO_LABEL, STATUS.OK)

    def go_to(self, position: int) -> bool:
        """Перемещение в заданное положение по кратчайшему пути."""

        return self._set_param(POWERSTEP01.GO_TO, STATUS.OK, position)

    def reset_pos(self) -> bool:
        """Обнуление счетчика текущего положения."""

        return self._set_param(POWERSTEP01.RESET_POS, STATUS.OK)

    def reset_powerstep01(self) -> bool:
        """Полный аппаратный и программный сброс модуля управления шаговым
        двигателем, но не контроллера в целом.
        """

        return self._set_param(POWERSTEP01.RESET_POWERSTEP01, STATUS.OK)

    def soft_stop(self) -> bool:
        """Плавная остановка двигателя с заданным ускорением."""

        return self._set_param(POWERSTEP01.SOFT_STOP, STATUS.OK)

    def hard_stop(self) -> bool:
        """Резкая остановка шагового двигателя."""

        return self._set_param(POWERSTEP01.HARD_STOP, STATUS.OK)

    def soft_hi_z(self) -> bool:
        """Плавная остановка шагового двигателя с заданным ускорением."""

        return self._set_param(POWERSTEP01.SOFT_HI_Z, STATUS.OK)

    def hard_hi_z(self) -> bool:
        """Резкая остановка и обесточивания обмоток двигателя."""

        return self._set_param(POWERSTEP01.HARD_HI_Z, STATUS.OK)

    def set_fs_speed(self, speed: int) -> bool:
        """Установка скорости перехода на полношаговый режим работы."""

        return self._set_param(POWERSTEP01.SET_FS_SPEED, STATUS.OK, speed)

    def set_wait(self, time: int) -> bool:
        """Задание паузы."""

        return self._set_param(POWERSTEP01.SET_WAIT, STATUS.OK, time)

    def set_rele(self) -> bool:
        """Включение реле контроллера."""

        return self._set_param(POWERSTEP01.SET_RELE, STATUS.STATUS_RELE_SET)

    def clr_rele(self) -> bool:
        """Выключение реле контроллера."""

        return self._set_param(POWERSTEP01.CLR_RELE, STATUS.STATUS_RELE_CLR)

    def get_rele(self) -> int:
        """Запрос состояния реле контроллера."""

        try:
            self._get_param(POWERSTEP01.GET_RELE, STATUS.OK)
        except SmsdError as err:
            if str(err) == "STATUS_RELE_CLR":
                return 0
            if str(err) == "STATUS_RELE_SET":
                return 1

        raise SmsdError

    def wait_in0(self) -> bool:
        """Ожидание поступления сигнала на вход IN0."""

        return self._set_param(POWERSTEP01.WAIT_IN0, STATUS.OK)

    def wait_in1(self) -> bool:
        """Ожидание поступления сигнала на вход IN1."""

        return self._set_param(POWERSTEP01.WAIT_IN1, STATUS.OK)

    def step_clock(self) -> bool:
        """Изменение режима управления двигателем на импульсное сигналами
        EN, STEP, DIR.
        """

        return self._set_param(POWERSTEP01.STEP_CLOCK, STATUS.OK)

    def stop_usb(self) -> bool:
        """Остановка работы микросхемы USB."""

        return self._set_param(POWERSTEP01.STOP_USB, STATUS.END_PROGRAMS)

    def get_stack(self) -> dict[str, int]:
        """Чтение информации о выполняемой в данный момент программе."""

        result = self._get_param(POWERSTEP01.GET_STACK, STATUS.GET_STACK)
        return {"command": result & 0xFF,
                "program": result >> 8 & 0x3}

    def wait_continue(self) -> bool:
        """Ожидание прихода синхросигнала на вход CONTINUE."""

        return self._set_param(POWERSTEP01.WAIT_CONTINUE, STATUS.OK)

    def set_wait_2(self, time: int) -> bool:
        """Задание паузы (может быть прервано поступлением сигнала на вход
        IN0, IN1 или SET_ZERO).
        """

        return self._set_param(POWERSTEP01.SET_WAIT_2, STATUS.OK, time)

    def scan_mark2_f(self, speed: int) -> bool:
        """Поиск метки положения в прямом направлении."""

        return self._set_param(POWERSTEP01.SCAN_MARK2_F, STATUS.OK, speed)

    def scan_mark2_r(self, speed: int) -> bool:
        """Поиск метки положения в обратном направлении."""

        return self._set_param(POWERSTEP01.SCAN_MARK2_R, STATUS.OK, speed)

    def goto_program_if_zero(self, program: int, command: int) -> bool:
        """Переход к заданной команде заданной программы, если значение
        текущей позиции равно 0.
        """

        return self._set_param(POWERSTEP01.GOTO_PROGRAM_IF_ZERO, STATUS.OK,
                               program << 8 | command)

    def goto_program_if_in_zero(self, program: int, command: int) -> bool:
        """Переход к заданной команде заданной программы, если на входе
        SET_ZERO присутствует сигнал.
        """

        return self._set_param(POWERSTEP01.GOTO_PROGRAM_IF_IN_ZERO, STATUS.OK,
                               program << 8 | command)

    def stop_program_mem(self) -> bool:
        """Остановка выполнения программы."""

        return self._set_param(POWERSTEP01.STOP_PROGRAM_MEM, STATUS.OK)

    def start_program_mem0(self) -> bool:
        """Старт программы, записанной в область памяти 0 контроллера."""

        return self._set_param(POWERSTEP01.START_PROGRAM_MEM0, STATUS.OK)

    def start_program_mem1(self) -> bool:
        """Старт программы, записанной в область памяти 1 контроллера."""

        return self._set_param(POWERSTEP01.START_PROGRAM_MEM1, STATUS.OK)

    def start_program_mem2(self) -> bool:
        """Старт программы, записанной в область памяти 2 контроллера."""

        return self._set_param(POWERSTEP01.START_PROGRAM_MEM2, STATUS.OK)

    def start_program_mem3(self) -> bool:
        """Старт программы, записанной в область памяти 3 контроллера."""

        return self._set_param(POWERSTEP01.START_PROGRAM_MEM3, STATUS.OK)

    def goto_program(self, program: int, command: int) -> bool:
        """Безусловный переход к заданной команде заданной программы."""

        return self._set_param(POWERSTEP01.GOTO_PROGRAM, STATUS.OK,
                               program << 8 | command)

    def goto_program_if_in0(self, program: int, command: int) -> bool:
        """Переход к заданной команде заданной программы, если на входе IN0
        присутствует сигнал.
        """

        return self._set_param(POWERSTEP01.GOTO_PROGRAM_IF_IN0, STATUS.OK,
                               program << 8 | command)

    def goto_program_if_in1(self, program: int, command: int) -> bool:
        """Переход к заданной команде заданной программы, если на входе IN1
        присутствует сигнал.
        """

        return self._set_param(POWERSTEP01.GOTO_PROGRAM_IF_IN1, STATUS.OK,
                               program << 8 | command)

    def call_program(self, program: int, command: int) -> bool:
        """Вызов подпрограммы."""

        return self._set_param(POWERSTEP01.CALL_PROGRAM, STATUS.OK,
                               program << 8 | command)

    def return_program(self) -> bool:
        """Возврат из подпрограммы в основную программу."""

        return self._set_param(POWERSTEP01.RETURN_PROGRAM, STATUS.OK)

    def loop_program(self, cycles: int, commands: int) -> bool:
        """Контроллер повторяет заданное число раз заданное количество команд."""

        return self._set_param(POWERSTEP01.LOOP_PROGRAM, STATUS.OK,
                               cycles << 10 | commands)

    def read_memory0(self) -> MEMORY_BANK:
        """Чтение списка исполнительных программ из банка памяти 0 контроллера."""

        return self._get_structure(CODE_CMD.POWERSTEP01_R_MEM0, MEMORY_BANK)

    def read_memory1(self) -> MEMORY_BANK:
        """Чтение списка исполнительных программ из банка памяти 1 контроллера."""

        return self._get_structure(CODE_CMD.POWERSTEP01_R_MEM1, MEMORY_BANK)

    def read_memory2(self) -> MEMORY_BANK:
        """Чтение списка исполнительных программ из банка памяти 2 контроллера."""

        return self._get_structure(CODE_CMD.POWERSTEP01_R_MEM2, MEMORY_BANK)

    def read_memory3(self) -> MEMORY_BANK:
        """Чтение списка исполнительных программ из банка памяти 3 контроллера."""

        return self._get_structure(CODE_CMD.POWERSTEP01_R_MEM3, MEMORY_BANK)

    def write_memory0(self, bank: MEMORY_BANK) -> bool:
        """Запись списка исполнительных программ в банк памяти 0 контроллера."""

        return self._set_structure(CODE_CMD.POWERSTEP01_W_MEM0, bank, STATUS.OK)

    def write_memory1(self, bank: MEMORY_BANK) -> bool:
        """Запись списка исполнительных программ в банк памяти 1 контроллера."""

        return self._set_structure(CODE_CMD.POWERSTEP01_W_MEM1, bank, STATUS.OK)

    def write_memory2(self, bank: MEMORY_BANK) -> bool:
        """Запись списка исполнительных программ в банк памяти 2 контроллера."""

        return self._set_structure(CODE_CMD.POWERSTEP01_W_MEM2, bank, STATUS.OK)

    def write_memory3(self, bank: MEMORY_BANK) -> bool:
        """Запись списка исполнительных программ в банк памяти 3 контроллера."""

        return self._set_structure(CODE_CMD.POWERSTEP01_W_MEM3, bank, STATUS.OK)


__all__ = ["Smsd"]
