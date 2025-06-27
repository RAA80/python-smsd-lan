#! /usr/bin/env python3

"""Реализация функций для работы с контроллером шагового двигателя SMSD-LAN."""

from __future__ import annotations

from ctypes import (POINTER, Array, Structure, byref, c_char, c_ubyte, cast,
                    create_string_buffer, sizeof, string_at)
from itertools import cycle
from typing import TypeVar

from smsd.protocol import (CMD_TYPE, COMMAND, COMMANDS_RETURN_DATA_TYPE,
                           ERROR_OR_COMMAND, LAN_COMMAND_TYPE, LAN_ERROR_STATISTICS,
                           MODE, SMSD_CMD_TYPE, SMSD_LAN_CONFIG_TYPE, STATUS_IN_EVENT)


class SmsdError(Exception):
    pass


T = TypeVar("T", bound=Structure)


class Smsd:
    """Класс функций для работы с контроллером шагового двигателя SMSD-LAN."""

    def __init__(self) -> None:
        """Инициализация класса Smsd."""

        self.version = self.get_version()
        self.cmd_id = cycle(range(256))

    def _bus_exchange(self, packet: bytes) -> bytes:
        """Обмен по интерфейсу."""

        raise NotImplementedError

    @staticmethod
    def _checksum(data: list[int]) -> int:
        """Вычисление контрольной суммы."""

        return -sum(data) & 0xFF

    def _make_request(self, command: CMD_TYPE, buffer: bytes) -> bytes:
        """Формирование пакета для записи."""

        lan_cmd_type = LAN_COMMAND_TYPE()
        lan_cmd_type.VER = self.version
        lan_cmd_type.TYPE = command.value
        lan_cmd_type.ID = next(self.cmd_id)
        lan_cmd_type.LENGTH = len(buffer)
        lan_cmd_type.DATA = (c_ubyte * 1024)(*buffer)
        lan_cmd_type.XOR = self._checksum([lan_cmd_type.VER,
                                           lan_cmd_type.TYPE,
                                           lan_cmd_type.ID,
                                           lan_cmd_type.LENGTH & 0xFF,
                                           lan_cmd_type.LENGTH >> 8,
                                          *lan_cmd_type.DATA[:lan_cmd_type.LENGTH]])
        structure_lenght = 6 + lan_cmd_type.LENGTH
        return string_at(byref(lan_cmd_type), structure_lenght)

    def _parse_answer(self, buffer: bytes) -> Array[c_char]:
        """Расшифровка прочитанного пакета."""

        data = create_string_buffer(buffer)
        lan_cmd_type = cast(data, POINTER(LAN_COMMAND_TYPE)).contents
        xor = self._checksum([lan_cmd_type.VER,
                              lan_cmd_type.TYPE,
                              lan_cmd_type.ID,
                              lan_cmd_type.LENGTH & 0xFF,
                              lan_cmd_type.LENGTH >> 8,
                             *lan_cmd_type.DATA[:lan_cmd_type.LENGTH]])
        if xor != lan_cmd_type.XOR:
            msg = "Invalid message checksum"
            raise SmsdError(msg)

        return create_string_buffer(bytes(lan_cmd_type.DATA[:lan_cmd_type.LENGTH]))

    @staticmethod
    def _check_error(err_or_cmd: ERROR_OR_COMMAND, structure: Structure) -> bool:
        """Проверка возвращаемого значения на ошибку."""

        if err_or_cmd.value != structure.ERROR_OR_COMMAND:
            msg = ERROR_OR_COMMAND(structure.ERROR_OR_COMMAND).name
            raise SmsdError(msg)
        return True

    def _execute(self, command: CMD_TYPE,
                       data: SMSD_CMD_TYPE | SMSD_LAN_CONFIG_TYPE | Array[c_ubyte] | Array[c_char],
                       ret_type: type[T]) -> T:
        """Выполнение команды и получение ответа."""

        buffer = string_at(byref(data), sizeof(data))
        request = self._make_request(command, buffer)
        answer = self._bus_exchange(request)
        ret_data = self._parse_answer(answer)

        return cast(ret_data, POINTER(ret_type)).contents

    def _password(self, command: CMD_TYPE, err_or_cmd: ERROR_OR_COMMAND,
                        password: str) -> bool:
        """Посылка команды авторизации в устройство."""

        data = (c_ubyte * 8)(*bytearray(password, encoding="ascii")[:8]) \
               if password else \
               (c_ubyte * 8)(*(0xEF, 0xCD, 0xAB, 0x89, 0x67, 0x45, 0x23, 0x01))

        structure = self._execute(command, data, COMMANDS_RETURN_DATA_TYPE)
        return self._check_error(err_or_cmd, structure)

    def _config_or_stats(self, command: CMD_TYPE, structure: type[T]) -> T:
        """Посылка команды чтения настроек или статистики."""

        data = create_string_buffer(0)
        return self._execute(command, data, structure)

    def _powerstep01(self, command: COMMAND, value: int,
                     err_or_cmd: ERROR_OR_COMMAND) -> COMMANDS_RETURN_DATA_TYPE:
        """Посылка команды POWERSTEP01."""

        smsd_cmd_type = SMSD_CMD_TYPE()
        smsd_cmd_type.COMMAND = command.value
        smsd_cmd_type.DATA = value

        result = self._execute(CMD_TYPE.CODE_CMD_POWERSTEP01, smsd_cmd_type,
                               COMMANDS_RETURN_DATA_TYPE)
        self._check_error(err_or_cmd, result)
        return result

    def _get_param(self, command: COMMAND, err_or_cmd: ERROR_OR_COMMAND) -> int:
        """Чтение значения параметра из устройства."""

        structure = self._powerstep01(command, 0, err_or_cmd)
        return int(structure.RETURN_DATA)

    def _set_param(self, command: COMMAND, err_or_cmd: ERROR_OR_COMMAND,
                         value: int = 0) -> bool:
        """Запись нового значения параметра в устройство."""

        self._powerstep01(command, value, err_or_cmd)
        return True

    # Основные функции

    def get_version(self) -> int:
        """Получение версии протокола."""

        if answer := self._bus_exchange(b""):
            return answer[1]

        msg = "Get protocol version error"
        raise SmsdError(msg)

    def authorization(self, password: str = "") -> bool:
        """Авторизация пользователя с помощью пароля. Если пароль не задан, то
        используется пароль по умолчанию.
        """

        return self._password(CMD_TYPE.CODE_CMD_REQUEST,
                              ERROR_OR_COMMAND.OK_ACCESS,
                              password)

    def set_password(self, password: str = "") -> bool:
        """Установка нового пароля для авторизации. Если новый пароль не задан,
        то устанавливается пароль по умолчанию.
        """

        return self._password(CMD_TYPE.CODE_CMD_PASSWORD_SET,
                              ERROR_OR_COMMAND.OK,
                              password)

    def get_lan_config(self) -> SMSD_LAN_CONFIG_TYPE:
        """Чтение текущих сетевых настроек."""

        return self._config_or_stats(CMD_TYPE.CODE_CMD_CONFIG_GET,
                                     SMSD_LAN_CONFIG_TYPE)

    def set_lan_config(self, config: SMSD_LAN_CONFIG_TYPE) -> bool:
        """Запись новых сетевых настроек."""

        structure = self._execute(CMD_TYPE.CODE_CMD_CONFIG_SET, config,
                                  COMMANDS_RETURN_DATA_TYPE)
        return self._check_error(ERROR_OR_COMMAND.OK, structure)

    def get_error_statistics(self) -> LAN_ERROR_STATISTICS:
        """Чтение из памяти контроллера информации о количестве включений
        рабочего режима контроллера и статистики по ошибкам.
        """

        return self._config_or_stats(CMD_TYPE.CODE_CMD_ERROR_GET,
                                     LAN_ERROR_STATISTICS)

    def get_max_speed(self) -> int:
        """Чтение текущего значения установленной максимальной скорости."""

        return self._get_param(COMMAND.CMD_POWERSTEP01_GET_MAX_SPEED,
                               ERROR_OR_COMMAND.COMMAND_GET_MAX_SPEED)

    def set_max_speed(self, speed: int) -> bool:
        """Установка максимальной скорости шагового двигателя."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SET_MAX_SPEED,
                               ERROR_OR_COMMAND.OK,
                               speed)

    def get_min_speed(self) -> int:
        """Чтение текущего значения установленной минимальной скорости."""

        return self._get_param(COMMAND.CMD_POWERSTEP01_GET_MIN_SPEED,
                               ERROR_OR_COMMAND.COMMAND_GET_MIN_SPEED)

    def set_min_speed(self, speed: int) -> bool:
        """Установка минимальной скорости вращения двигателя."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SET_MIN_SPEED,
                               ERROR_OR_COMMAND.OK,
                               speed)

    def get_speed(self) -> int:
        """Чтение текущего значения скорости."""

        return self._get_param(COMMAND.CMD_POWERSTEP01_GET_SPEED,
                               ERROR_OR_COMMAND.COMMAND_GET_SPEED)

    def run_f(self, speed: int) -> bool:
        """Старт непрерывного вращения двигателя в прямом направлении на
        указанной скорости.
        """

        return self._set_param(COMMAND.CMD_POWERSTEP01_RUN_F,
                               ERROR_OR_COMMAND.OK,
                               speed)

    def run_r(self, speed: int) -> bool:
        """Старт непрерывного вращения двигателя в обратном направлении на
        указанной скорости.
        """

        return self._set_param(COMMAND.CMD_POWERSTEP01_RUN_R,
                               ERROR_OR_COMMAND.OK,
                               speed)

    def get_mode(self) -> MODE:
        """Чтение настроек управления двигателем."""

        mode = MODE()
        mode.as_byte = self._get_param(COMMAND.CMD_POWERSTEP01_GET_MODE,
                                       ERROR_OR_COMMAND.COMMAND_GET_MODE)
        return mode

    def set_mode(self, mode: MODE) -> bool:
        """Установка параметров управления двигателем."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SET_MODE,
                               ERROR_OR_COMMAND.OK,
                               mode.as_byte)

    def set_acc(self, acceleration: int) -> bool:
        """Установка значения ускорения двигателя."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SET_ACC,
                               ERROR_OR_COMMAND.OK,
                               acceleration)

    def set_dec(self, deceleration: int) -> bool:
        """Установка значения замедления шагового двигателя."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SET_DEC,
                               ERROR_OR_COMMAND.OK,
                               deceleration)

    def move_f(self, steps: int) -> bool:
        """Перемещение двигателя в прямом направлении на указанную величину."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_MOVE_F,
                               ERROR_OR_COMMAND.OK,
                               steps)

    def move_r(self, steps: int) -> bool:
        """Перемещение двигателя в обратном направлении на указанную величину."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_MOVE_R,
                               ERROR_OR_COMMAND.OK,
                               steps)

    def get_abs_pos(self) -> int:
        """Чтение положения двигателя."""

        return self._get_param(COMMAND.CMD_POWERSTEP01_GET_ABS_POS,
                               ERROR_OR_COMMAND.COMMAND_GET_ABS_POS)

    def get_el_pos(self) -> int:
        """Чтение электрического положения ротора двигателя."""

        return self._get_param(COMMAND.CMD_POWERSTEP01_GET_EL_POS,
                               ERROR_OR_COMMAND.COMMAND_GET_EL_POS)

    def get_status_and_clr(self) -> int:
        """Чтение текущего статуса контроллера и сброса всех флагов ошибок."""

        return self._get_param(COMMAND.CMD_POWERSTEP01_GET_STATUS_AND_CLR,
                               ERROR_OR_COMMAND.OK)

    def get_status_in_event(self) -> STATUS_IN_EVENT:
        """Чтение текущего состояния входных сигналов."""

        status = STATUS_IN_EVENT()
        status.as_byte = self._get_param(COMMAND.CMD_POWERSTEP01_STATUS_IN_EVENT,
                                         ERROR_OR_COMMAND.COMMAND_GET_STATUS_IN_EVENT)
        return status

    def go_to_f(self, position: int) -> bool:
        """Перемещение в заданную позицию в прямом направлении."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_GO_TO_F,
                               ERROR_OR_COMMAND.OK,
                               position)

    def go_to_r(self, position: int) -> bool:
        """Перемещение в заданную позицию в обратном направлении."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_GO_TO_R,
                               ERROR_OR_COMMAND.OK,
                               position)

    def set_mask_event(self, mask: int) -> bool:
        """Маскирование входных сигналов."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SET_MASK_EVENT,
                               ERROR_OR_COMMAND.OK,
                               mask)

    def go_until_f(self, signal: int) -> bool:
        """Старт вращения двигателя в прямом направлении на максимальной
        скорости до получения сигнала на вход.
        """

        return self._set_param(COMMAND.CMD_POWERSTEP01_GO_UNTIL_F,
                               ERROR_OR_COMMAND.OK,
                               signal)

    def go_until_r(self, signal: int) -> bool:
        """Старт вращения двигателя в обратном направлении на максимальной
        скорости до получения сигнала на вход.
        """

        return self._set_param(COMMAND.CMD_POWERSTEP01_GO_UNTIL_R,
                               ERROR_OR_COMMAND.OK,
                               signal)

    def end(self) -> bool:
        """Обозначение конца программы."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_END,
                               ERROR_OR_COMMAND.END_PROGRAMS)

    def scan_zero_f(self, speed: int) -> bool:
        """Поиск нулевого положения в прямом направлении с заданной скоростью."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SCAN_ZERO_F,
                               ERROR_OR_COMMAND.OK,
                               speed)

    def scan_zero_r(self, speed: int) -> bool:
        """Поиск нулевого положения в обратном направлении с заданной скоростью."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SCAN_ZERO_R,
                               ERROR_OR_COMMAND.OK,
                               speed)

    def scan_label_f(self, speed: int) -> bool:
        """Поиск метки положения в прямом направлении."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SCAN_LABEL_F,
                               ERROR_OR_COMMAND.OK,
                               speed)

    def scan_label_r(self, speed: int) -> bool:
        """Поиск метки положения в обратном направлении."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SCAN_LABEL_R,
                               ERROR_OR_COMMAND.OK,
                               speed)

    def go_zero(self) -> bool:
        """Перемещение в нулевое положение."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_GO_ZERO,
                               ERROR_OR_COMMAND.OK)

    def go_label(self) -> bool:
        """Перемещение в положение, которое было отмечено как метка."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_GO_LABEL,
                               ERROR_OR_COMMAND.OK)

    def go_to(self, position: int) -> bool:
        """Перемещение в заданное положение по кратчайшему пути."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_GO_TO,
                               ERROR_OR_COMMAND.OK,
                               position)

    def reset_pos(self) -> bool:
        """Обнуление счетчика текущего положения."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_RESET_POS,
                               ERROR_OR_COMMAND.OK)

    def reset_powerstep01(self) -> bool:
        """Полный аппаратный и программный сброс модуля управления шаговым
        двигателем, но не контроллера в целом.
        """

        return self._set_param(COMMAND.CMD_POWERSTEP01_RESET_POWERSTEP01,
                               ERROR_OR_COMMAND.OK)

    def soft_stop(self) -> bool:
        """Плавная остановка двигателя с заданным ускорением."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SOFT_STOP,
                               ERROR_OR_COMMAND.OK)

    def hard_stop(self) -> bool:
        """Резкая остановка шагового двигателя."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_HARD_STOP,
                               ERROR_OR_COMMAND.OK)

    def soft_hi_z(self) -> bool:
        """Плавная остановка шагового двигателя с заданным ускорением."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SOFT_HI_Z,
                               ERROR_OR_COMMAND.OK)

    def hard_hi_z(self) -> bool:
        """Резкая остановка и обесточивания обмоток двигателя."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_HARD_HI_Z,
                               ERROR_OR_COMMAND.OK)

    def set_fs_speed(self, speed: int) -> bool:
        """Установка скорости перехода на полношаговый режим работы."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SET_FS_SPEED,
                               ERROR_OR_COMMAND.OK,
                               speed)

    def set_wait(self, time: int) -> bool:
        """Задание паузы."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SET_WAIT,
                               ERROR_OR_COMMAND.OK,
                               time)

    def set_rele(self) -> bool:
        """Включение реле контроллера."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SET_RELE,
                               ERROR_OR_COMMAND.STATUS_RELE_SET)

    def clr_rele(self) -> bool:
        """Выключение реле контроллера."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_CLR_RELE,
                               ERROR_OR_COMMAND.STATUS_RELE_CLR)

    def get_rele(self) -> int:
        """Запрос состояния реле контроллера."""

        try:
            self._get_param(COMMAND.CMD_POWERSTEP01_GET_RELE,
                            ERROR_OR_COMMAND.OK)
        except SmsdError as err:
            if str(err) == "STATUS_RELE_CLR":
                return 0
            if str(err) == "STATUS_RELE_SET":
                return 1

        raise SmsdError

    def wait_in0(self) -> bool:
        """Ожидание поступления сигнала на вход IN0."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_WAIT_IN0,
                               ERROR_OR_COMMAND.OK)

    def wait_in1(self) -> bool:
        """Ожидание поступления сигнала на вход IN1."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_WAIT_IN1,
                               ERROR_OR_COMMAND.OK)

    def step_clock(self) -> bool:
        """Изменение режима управления двигателем на импульсное сигналами
        EN, STEP, DIR.
        """

        return self._set_param(COMMAND.CMD_POWERSTEP01_STEP_CLOCK,
                               ERROR_OR_COMMAND.OK)

    def stop_usb(self) -> bool:
        """Остановка работы микросхемы USB."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_STOP_USB,
                               ERROR_OR_COMMAND.END_PROGRAMS)

    def get_stack(self) -> dict[str, int]:
        """Чтение информации о выполняемой в данный момент программе."""

        result = self._get_param(COMMAND.CMD_POWERSTEP01_GET_STACK,
                                 ERROR_OR_COMMAND.COMMAND_GET_STACK)
        return {"command": result & 0xFF,
                "program": result >> 8 & 0x3}

    def wait_continue(self) -> bool:
        """Ожидание прихода синхросигнала на вход CONTINUE."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_WAIT_CONTINUE,
                               ERROR_OR_COMMAND.OK)

    def set_wait_2(self, time: int) -> bool:
        """Задание паузы (может быть прервано поступлением сигнала на вход
        IN0, IN1 или SET_ZERO).
        """

        return self._set_param(COMMAND.CMD_POWERSTEP01_SET_WAIT_2,
                               ERROR_OR_COMMAND.OK,
                               time)

    def scan_mark2_f(self, speed: int) -> bool:
        """Поиск метки положения в прямом направлении."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SCAN_MARK2_F,
                               ERROR_OR_COMMAND.OK,
                               speed)

    def scan_mark2_r(self, speed: int) -> bool:
        """Поиск метки положения в обратном направлении."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SCAN_MARK2_R,
                               ERROR_OR_COMMAND.OK,
                               speed)

    def goto_program_if_zero(self, program: int, command: int) -> bool:
        """Переход к заданной команде заданной программы, если значение
        текущей позиции равно 0.
        """

        return self._set_param(COMMAND.CMD_POWERSTEP01_GOTO_PROGRAM_IF_ZERO,
                               ERROR_OR_COMMAND.OK,
                               program << 8 | command)

    def goto_program_if_in_zero(self, program: int, command: int) -> bool:
        """Переход к заданной команде заданной программы, если на входе
        SET_ZERO присутствует сигнал.
        """

        return self._set_param(COMMAND.CMD_POWERSTEP01_GOTO_PROGRAM_IF_IN_ZERO,
                               ERROR_OR_COMMAND.OK,
                               program << 8 | command)

    def stop_program_mem(self) -> bool:
        """Остановка выполнения программы."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_STOP_PROGRAM_MEM,
                               ERROR_OR_COMMAND.OK)

    def start_program_mem0(self) -> bool:
        """Старт программы, записанной в область памяти 0 контроллера."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_START_PROGRAM_MEM0,
                               ERROR_OR_COMMAND.OK)

    def start_program_mem1(self) -> bool:
        """Старт программы, записанной в область памяти 1 контроллера."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_START_PROGRAM_MEM1,
                               ERROR_OR_COMMAND.OK)

    def start_program_mem2(self) -> bool:
        """Старт программы, записанной в область памяти 2 контроллера."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_START_PROGRAM_MEM2,
                               ERROR_OR_COMMAND.OK)

    def start_program_mem3(self) -> bool:
        """Старт программы, записанной в область памяти 3 контроллера."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_START_PROGRAM_MEM3,
                               ERROR_OR_COMMAND.OK)

    def goto_program(self, program: int, command: int) -> bool:
        """Безусловный переход к заданной команде заданной программы."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_GOTO_PROGRAM,
                               ERROR_OR_COMMAND.OK,
                               program << 8 | command)

    def goto_program_if_in0(self, program: int, command: int) -> bool:
        """Переход к заданной команде заданной программы, если на входе IN0
        присутствует сигнал.
        """

        return self._set_param(COMMAND.CMD_POWERSTEP01_GOTO_PROGRAM_IF_IN0,
                               ERROR_OR_COMMAND.OK,
                               program << 8 | command)

    def goto_program_if_in1(self, program: int, command: int) -> bool:
        """Переход к заданной команде заданной программы, если на входе IN1
        присутствует сигнал.
        """

        return self._set_param(COMMAND.CMD_POWERSTEP01_GOTO_PROGRAM_IF_IN1,
                               ERROR_OR_COMMAND.OK,
                               program << 8 | command)

    def call_program(self, program: int, command: int) -> bool:
        """Вызов подпрограммы."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_CALL_PROGRAM,
                               ERROR_OR_COMMAND.OK,
                               program << 8 | command)

    def return_program(self) -> bool:
        """Возврат из подпрограммы в основную программу."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_RETURN_PROGRAM,
                               ERROR_OR_COMMAND.OK)

    def loop_program(self, cycles: int, commands: int) -> bool:
        """Контроллер повторяет заданное число раз заданное количество команд."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_LOOP_PROGRAM,
                               ERROR_OR_COMMAND.OK,
                               cycles << 10 | commands)


__all__ = ["Smsd"]
