#! /usr/bin/env python3

"""Реализация функций для работы с контроллером шагового двигателя SMSD-LAN
по протоколу Modbus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from smsd.exception import SmsdError
from smsd.protocol import (LAN_ERROR_STATISTICS, MEMORY_BANK, MODE,
                           POWERSTEP01, POWERSTEP_STATUS_TYPEDEF,
                           SMSD_LAN_CONFIG_TYPE, STATUS_IN_EVENT)

if TYPE_CHECKING:
    from pymodbus.pdu import ModbusPDU


class Modbus:
    """Класс функций для работы с контроллером шагового двигателя SMSD-LAN
    по протоколу Modbus.
    """

    def __init__(self) -> None:
        """Инициализация класса Modbus."""

        self._version = self._get_version()

    def _write_bit(self, address: int, values: list[bool]) -> ModbusPDU:
        """Запись в битовый регистр Modbus."""

        raise NotImplementedError

    def _write_hr(self, address: int, values: list[int]) -> ModbusPDU:
        """Запись в регистр Modbus."""

        raise NotImplementedError

    def _read_hr(self, address: int, count: int) -> ModbusPDU:
        """Запись в регистр Modbus."""

        raise NotImplementedError

    def _read_di(self, address: int, count: int) -> ModbusPDU:
        """Чтение дискретных входов."""

        raise NotImplementedError

    def _get_version(self) -> int:
        """Получение версии протокола."""

        result = self._read_hr(address=0x8002, count=1)
        return result.registers[0]

    @staticmethod
    def _check_error(retcode: ModbusPDU) -> ModbusPDU:
        """Проверка возвращаемого значения на ошибку."""

        if retcode.isError():
            raise SmsdError(retcode)
        return retcode

    def _authorization(self, password: str, mode: int) -> bool:
        """Авторизация/Установка пароля пользователя."""

        data = list(bytearray(password, encoding="ascii")[:8]) \
               if password else \
               [0xEF, 0xCD, 0xAB, 0x89, 0x67, 0x45, 0x23, 0x01]
        self._run_cmd(0x2100, data, 0x2104, [mode])

        result = self._read_di(address=0x2200, count=1)
        if not result.bits[0]:
            msg = "Authorization Error"
            raise SmsdError(msg)

        return True

    def _run_cmd(self, address1: int,
                       arg1: list[int],
                       address2: int | None = None,
                       arg2: list[int] | None = None) -> bool:
        """Запись в регистр для начала выполнения команды."""

        self._write_hr(address=address1, values=arg1)
        if address2 is not None and arg2 is not None:
            self._write_hr(address=address2, values=arg2)
        return True

    # Основные функции

    def authorization(self, password: str = "") -> bool:
        """Авторизация пользователя с помощью пароля. Если значение не задано, то
        используется пароль по умолчанию.
        """

        return self._authorization(password, 0)

    def set_password(self, password: str = "") -> bool:
        """Установка нового пароля авторизации. Если значение не задано, то
        устанавливается пароль по умолчанию.
        """

        return self._authorization(password, 1)

    def get_lan_config(self) -> SMSD_LAN_CONFIG_TYPE:
        """Чтение текущих сетевых настроек."""

        result = self._read_hr(address=0x7001, count=24)

        config = SMSD_LAN_CONFIG_TYPE()
        config.MAC = result.registers[:6]
        config.IP = result.registers[6:10]
        config.SN = result.registers[10:14]
        config.GW = result.registers[14:18]
        config.DNS = result.registers[18:22]
        config.PORT = result.registers[22]
        config.DHCP = result.registers[23]

        return config

    def set_lan_config(self, config: SMSD_LAN_CONFIG_TYPE) -> bool:
        """Запись новых сетевых настроек."""

        return self._run_cmd(address1=0x7001, arg1=[*list(config.MAC),
                                                    *list(config.IP),
                                                    *list(config.SN),
                                                    *list(config.GW),
                                                    *list(config.DNS),
                                                    *list(config.PORT),
                                                    *list(config.DHCP)],
                             address2=0x7400, arg2=[1])

    def get_error_statistics(self) -> LAN_ERROR_STATISTICS:
        """Чтение из памяти контроллера информации о количестве включений
        рабочего режима контроллера и статистики по ошибкам.
        """

        raise NotImplementedError

    def get_max_speed(self) -> int:
        """Чтение текущего значения установленной максимальной скорости."""

        result = self._read_hr(address=0x1101, count=1)
        return result.registers[0]

    def set_max_speed(self, speed: int) -> bool:
        """Установка максимальной скорости шагового двигателя."""

        return self._run_cmd(0x1101, [speed])

    def get_min_speed(self) -> int:
        """Чтение текущего значения установленной минимальной скорости."""

        result = self._read_hr(address=0x1100, count=1)
        return result.registers[0]

    def set_min_speed(self, speed: int) -> bool:
        """Установка минимальной скорости вращения двигателя."""

        return self._run_cmd(0x1100, [speed])

    def get_speed(self) -> int:
        """Чтение текущего значения скорости."""

        result = self._read_hr(address=0x1000, count=1)
        return result.registers[0]

    def run_f(self, speed: int) -> bool:
        """Старт непрерывного вращения двигателя в прямом направлении на
        указанной скорости.
        """

        return self._run_cmd(0x1105, [speed],
                             0x1109, [POWERSTEP01.RUN_F])

    def run_r(self, speed: int) -> bool:
        """Старт непрерывного вращения двигателя в обратном направлении на
        указанной скорости.
        """

        return self._run_cmd(0x1105, [speed],
                             0x1109, [POWERSTEP01.RUN_R])

    def get_mode(self) -> MODE:
        """Чтение настроек управления двигателем."""

        result = self._read_hr(address=0x110A, count=5)

        mode = MODE()
        mode.CURRENT_OR_VOLTAGE = result.registers[0]
        mode.MOTOR_TYPE = result.registers[1]
        mode.MICROSTEPPING = result.registers[2]
        mode.WORK_CURRENT = result.registers[3]
        mode.STOP_CURRENT = result.registers[4]
        mode.PROGRAM_N = 0

        return mode

    def set_mode(self, mode: MODE) -> bool:
        """Установка параметров управления двигателем."""

        return self._run_cmd(0x110A, [mode.CURRENT_OR_VOLTAGE,
                                      mode.MOTOR_TYPE,
                                      mode.MICROSTEPPING,
                                      mode.WORK_CURRENT,
                                      mode.STOP_CURRENT])

    def set_acc(self, acceleration: int) -> bool:
        """Установка значения ускорения двигателя."""

        return self._run_cmd(0x1102, [acceleration])

    def set_dec(self, deceleration: int) -> bool:
        """Установка значения замедления шагового двигателя."""

        return self._run_cmd(0x1103, [deceleration])

    def move_f(self, steps: int) -> bool:
        """Перемещение двигателя в прямом направлении на указанную величину."""

        return self._run_cmd(0x1106, [*steps.to_bytes(2, "big")],
                             0x1109, [POWERSTEP01.MOVE_F])

    def move_r(self, steps: int) -> bool:
        """Перемещение двигателя в обратном направлении на указанную величину."""

        return self._run_cmd(0x1106, [*steps.to_bytes(2, "big")],
                             0x1109, [POWERSTEP01.MOVE_R])

    def get_abs_pos(self) -> int:
        """Чтение положения двигателя."""

        result = self._read_hr(address=0x1001, count=2)
        return int.from_bytes(result.registers, "big")

    def get_el_pos(self) -> int:
        """Чтение электрического положения ротора двигателя."""

        result = self._read_hr(address=0x1003, count=1)
        return result.registers[0]

    def get_status_and_clr(self) -> int:
        """Чтение текущего статуса контроллера и сброса всех флагов ошибок."""

        self._write_bit(address=0x1400, values=[True])
        result = self._read_hr(address=0x1004, count=1)
        return result.registers[0]

    def get_status_in_event(self) -> STATUS_IN_EVENT:
        """Чтение текущего состояния входных сигналов."""

        inputs = self._read_hr(address=0x1005, count=1)
        mask = self._read_hr(address=0x110F, count=1)
        wait = self._read_hr(address=0x1110, count=1)

        status = STATUS_IN_EVENT()
        status.INT_0 = inputs.registers[0] >> 0 & 1
        status.INT_1 = inputs.registers[0] >> 1 & 1
        status.INT_2 = inputs.registers[0] >> 2 & 1
        status.INT_3 = inputs.registers[0] >> 3 & 1
        status.INT_4 = inputs.registers[0] >> 4 & 1
        status.INT_5 = inputs.registers[0] >> 5 & 1
        status.INT_6 = inputs.registers[0] >> 6 & 1
        status.INT_7 = inputs.registers[0] >> 7 & 1
        status.MASK_0 = mask.registers[0] >> 0 & 1
        status.MASK_1 = mask.registers[0] >> 1 & 1
        status.MASK_2 = mask.registers[0] >> 2 & 1
        status.MASK_3 = mask.registers[0] >> 3 & 1
        status.MASK_4 = mask.registers[0] >> 4 & 1
        status.MASK_5 = mask.registers[0] >> 5 & 1
        status.MASK_6 = mask.registers[0] >> 6 & 1
        status.MASK_7 = mask.registers[0] >> 7 & 1
        status.WAIT_0 = wait.registers[0] >> 0 & 1
        status.WAIT_1 = wait.registers[0] >> 1 & 1
        status.WAIT_2 = wait.registers[0] >> 2 & 1
        status.WAIT_3 = wait.registers[0] >> 3 & 1
        status.WAIT_4 = wait.registers[0] >> 4 & 1
        status.WAIT_5 = wait.registers[0] >> 5 & 1
        status.WAIT_6 = wait.registers[0] >> 6 & 1
        status.WAIT_7 = wait.registers[0] >> 7 & 1

        return status

    def go_to_f(self, position: int) -> bool:
        """Перемещение в заданную позицию в прямом направлении."""

        return self._run_cmd(0x1106, [*position.to_bytes(2, "big")],
                             0x1109, [POWERSTEP01.GO_TO_F])

    def go_to_r(self, position: int) -> bool:
        """Перемещение в заданную позицию в обратном направлении."""

        return self._run_cmd(0x1106, [*position.to_bytes(2, "big")],
                             0x1109, [POWERSTEP01.GO_TO_R])

    def set_mask_event(self, mask: int) -> bool:
        """Маскирование входных сигналов."""

        raise NotImplementedError

    def go_until_f(self, signal: int) -> bool:
        """Старт вращения двигателя в прямом направлении на максимальной
        скорости до получения сигнала на вход.
        """

        return self._run_cmd(0x1108, [signal],
                             0x1109, [POWERSTEP01.GO_UNTIL_F])

    def go_until_r(self, signal: int) -> bool:
        """Старт вращения двигателя в обратном направлении на максимальной
        скорости до получения сигнала на вход.
        """

        return self._run_cmd(0x1108, [signal],
                             0x1109, [POWERSTEP01.GO_UNTIL_R])

    def end(self) -> bool:
        """Обозначение конца программы."""

        raise NotImplementedError

    def scan_zero_f(self, speed: int) -> bool:
        """Поиск нулевого положения в прямом направлении с заданной скоростью."""

        return self._run_cmd(0x1105, [speed],
                             0x1109, [POWERSTEP01.SCAN_ZERO_F])

    def scan_zero_r(self, speed: int) -> bool:
        """Поиск нулевого положения в обратном направлении с заданной скоростью."""

        return self._run_cmd(0x1105, [speed],
                             0x1109, [POWERSTEP01.SCAN_ZERO_R])

    def scan_label_f(self, speed: int) -> bool:
        """Поиск метки положения в прямом направлении."""

        return self._run_cmd(0x1105, [speed],
                             0x1109, [POWERSTEP01.SCAN_LABEL_F])

    def scan_label_r(self, speed: int) -> bool:
        """Поиск метки положения в обратном направлении."""

        return self._run_cmd(0x1105, [speed],
                             0x1109, [POWERSTEP01.SCAN_LABEL_R])

    def go_zero(self) -> bool:
        """Перемещение в нулевое положение."""

        return self._run_cmd(0x1109, [POWERSTEP01.GO_ZERO])

    def go_label(self) -> bool:
        """Перемещение в положение, которое было отмечено как метка."""

        return self._run_cmd(0x1109, [POWERSTEP01.GO_LABEL])

    def go_to(self, position: int) -> bool:
        """Перемещение в заданное положение по кратчайшему пути."""

        return self._run_cmd(0x1106, [*position.to_bytes(2, "big")],
                             0x1109, [POWERSTEP01.GO_TO])

    def reset_pos(self) -> bool:
        """Обнуление счетчика текущего положения."""

        self._write_bit(address=0x1401, values=[True])
        return True

    def reset_powerstep01(self) -> bool:
        """Полный аппаратный и программный сброс модуля управления шаговым
        двигателем, но не контроллера в целом.
        """

        self._write_bit(address=0x1402, values=[True])
        return True

    def soft_stop(self) -> bool:
        """Плавная остановка двигателя с заданным ускорением."""

        return self._run_cmd(0x1109, [POWERSTEP01.SOFT_STOP])

    def hard_stop(self) -> bool:
        """Резкая остановка шагового двигателя."""

        return self._run_cmd(0x1109, [POWERSTEP01.HARD_STOP])

    def soft_hi_z(self) -> bool:
        """Плавная остановка шагового двигателя с заданным ускорением."""

        return self._run_cmd(0x1109, [POWERSTEP01.SOFT_HI_Z])

    def hard_hi_z(self) -> bool:
        """Резкая остановка и обесточивания обмоток двигателя."""

        return self._run_cmd(0x1109, [POWERSTEP01.HARD_HI_Z])

    def set_fs_speed(self, speed: int) -> bool:
        """Установка скорости перехода на полношаговый режим работы."""

        return self._run_cmd(0x1104, [speed])

    def set_wait(self, time: int) -> bool:
        """Задание паузы."""

        raise NotImplementedError

    def set_rele(self) -> bool:
        """Включение реле контроллера."""

        self._write_bit(address=0x1407, values=[True])
        return True

    def clr_rele(self) -> bool:
        """Выключение реле контроллера."""

        self._write_bit(address=0x1407, values=[False])
        return True

    def get_rele(self) -> int:
        """Запрос состояния реле контроллера."""

        result = self._read_di(address=0x1407, count=1)
        return int(result.bits[0])

    def wait_in0(self) -> bool:
        """Ожидание поступления сигнала на вход IN0."""

        raise NotImplementedError

    def wait_in1(self) -> bool:
        """Ожидание поступления сигнала на вход IN1."""

        raise NotImplementedError

    def step_clock(self) -> bool:
        """Изменение режима управления двигателем на импульсное сигналами
        EN, STEP, DIR.
        """

        raise NotImplementedError

    def stop_usb(self) -> bool:
        """Остановка работы микросхемы USB."""

        raise NotImplementedError

    def get_stack(self) -> dict[str, int]:
        """Чтение информации о выполняемой в данный момент программе."""

        result = self._read_hr(address=0x3001, count=2)
        return {"command": result.registers[1],
                "program": result.registers[0]}

    def wait_continue(self) -> bool:
        """Ожидание прихода синхросигнала на вход CONTINUE."""

        raise NotImplementedError

    def set_wait_2(self, time: int) -> bool:
        """Задание паузы (может быть прервано поступлением сигнала на вход
        IN0, IN1 или SET_ZERO).
        """

        raise NotImplementedError

    def scan_mark2_f(self, speed: int) -> bool:
        """Поиск метки положения в прямом направлении."""

        return self._run_cmd(0x1105, [speed],
                             0x1109, [POWERSTEP01.SCAN_MARK2_F])

    def scan_mark2_r(self, speed: int) -> bool:
        """Поиск метки положения в обратном направлении."""

        return self._run_cmd(0x1105, [speed],
                             0x1109, [POWERSTEP01.SCAN_MARK2_R])

    def goto_program_if_zero(self, program: int, command: int) -> bool:
        """Переход к заданной команде заданной программы, если значение
        текущей позиции равно 0.
        """

        raise NotImplementedError

    def goto_program_if_in_zero(self, program: int, command: int) -> bool:
        """Переход к заданной команде заданной программы, если на входе
        SET_ZERO присутствует сигнал.
        """

        raise NotImplementedError

    def stop_program_mem(self) -> bool:
        """Остановка выполнения программы."""

        return self._run_cmd(0x1109, [POWERSTEP01.STOP_PROGRAM_MEM])

    def start_program_mem0(self) -> bool:
        """Старт программы, записанной в область памяти 0 контроллера."""

        return self._run_cmd(0x1109, [POWERSTEP01.START_PROGRAM_MEM0])

    def start_program_mem1(self) -> bool:
        """Старт программы, записанной в область памяти 1 контроллера."""

        return self._run_cmd(0x1109, [POWERSTEP01.START_PROGRAM_MEM1])

    def start_program_mem2(self) -> bool:
        """Старт программы, записанной в область памяти 2 контроллера."""

        return self._run_cmd(0x1109, [POWERSTEP01.START_PROGRAM_MEM2])

    def start_program_mem3(self) -> bool:
        """Старт программы, записанной в область памяти 3 контроллера."""

        return self._run_cmd(0x1109, [POWERSTEP01.START_PROGRAM_MEM3])

    def goto_program(self, program: int, command: int) -> bool:
        """Безусловный переход к заданной команде заданной программы."""

        raise NotImplementedError

    def goto_program_if_in0(self, program: int, command: int) -> bool:
        """Переход к заданной команде заданной программы, если на входе IN0
        присутствует сигнал.
        """
        raise NotImplementedError

    def goto_program_if_in1(self, program: int, command: int) -> bool:
        """Переход к заданной команде заданной программы, если на входе IN1
        присутствует сигнал.
        """

        raise NotImplementedError

    def call_program(self, program: int, command: int) -> bool:
        """Вызов подпрограммы."""

        raise NotImplementedError

    def return_program(self) -> bool:
        """Возврат из подпрограммы в основную программу."""

        raise NotImplementedError

    def loop_program(self, cycles: int, commands: int) -> bool:
        """Контроллер повторяет заданное число раз заданное количество команд."""

        raise NotImplementedError

    def read_memory0(self) -> MEMORY_BANK:
        """Чтение списка исполнительных программ из банка памяти 0 контроллера."""

        raise NotImplementedError

    def read_memory1(self) -> MEMORY_BANK:
        """Чтение списка исполнительных программ из банка памяти 1 контроллера."""

        raise NotImplementedError

    def read_memory2(self) -> MEMORY_BANK:
        """Чтение списка исполнительных программ из банка памяти 2 контроллера."""

        raise NotImplementedError

    def read_memory3(self) -> MEMORY_BANK:
        """Чтение списка исполнительных программ из банка памяти 3 контроллера."""

        raise NotImplementedError

    def write_memory0(self, bank: MEMORY_BANK) -> bool:
        """Запись списка исполнительных программ в банк памяти 0 контроллера."""

        raise NotImplementedError

    def write_memory1(self, bank: MEMORY_BANK) -> bool:
        """Запись списка исполнительных программ в банк памяти 1 контроллера."""

        raise NotImplementedError

    def write_memory2(self, bank: MEMORY_BANK) -> bool:
        """Запись списка исполнительных программ в банк памяти 2 контроллера."""

        raise NotImplementedError

    def write_memory3(self, bank: MEMORY_BANK) -> bool:
        """Запись списка исполнительных программ в банк памяти 3 контроллера."""

        raise NotImplementedError

    @property
    def status_powerstep01(self) -> POWERSTEP_STATUS_TYPEDEF:
        """Статус состояния процесса управления шаговым двигателем."""

        result = self._read_di(address=0x1200, count=10)
        status = POWERSTEP_STATUS_TYPEDEF()

        if result.bits[1]:
            mot_status = 0
        elif result.bits[2]:
            mot_status = 3
        elif result.bits[3]:
            mot_status = 1
        elif result.bits[4]:
            mot_status = 2

        status.HIZ = result.bits[0]
        status.BUSY = result.bits[5]
        status.SW_F = result.bits[6]
        status.SW_EVN = result.bits[7]
        status.DIR = result.bits[8]
        status.MOT_STATUS = mot_status
        status.CMD_ERROR = result.bits[9]

        return status


__all__ = ["Modbus"]
