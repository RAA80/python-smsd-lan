#! /usr/bin/env python3

"""Реализация функций для работы с контроллером шагового двигателя SMSD-LAN."""

from copy import deepcopy
from ctypes import (POINTER, byref, c_ubyte, cast, create_string_buffer,
                    sizeof, string_at)
from itertools import cycle

from .protocol import (CMD_TYPE, COMMAND, COMMANDS_RETURN_DATA_TYPE,
                       ERROR_OR_COMMAND, LAN_COMMAND_TYPE, LAN_ERROR_STATISTICS,
                       SMSD_CMD_TYPE, SMSD_LAN_CONFIG_TYPE)


class SMSDError(Exception):
    pass


class Smsd:
    """Класс функций для работы с контроллером шагового двигателя SMSD-LAN."""

    def __init__(self):
        """Инициализация класса Smsd."""

        self.version = None
        self.cmd_id = cycle(range(256))

    def _bus_exchange(self, packet):
        """Обмен по интерфейсу."""

        raise NotImplementedError

    @staticmethod
    def _checksum(data):
        """Вычисление контрольной суммы."""

        return -sum(data) & 0xFF

    def _make_request(self, command, length, buffer):
        """Формирование пакета для записи."""

        data = (c_ubyte * 1024)(*bytearray(buffer))

        lan_command_type = LAN_COMMAND_TYPE()
        lan_command_type.VER = self.version
        lan_command_type.TYPE = command.value
        lan_command_type.ID = next(self.cmd_id)
        lan_command_type.LENGTH = length
        lan_command_type.DATA = data
        lan_command_type.XOR = self._checksum([lan_command_type.VER,
                                               lan_command_type.TYPE,
                                               lan_command_type.ID,
                                               lan_command_type.LENGTH & 0xFF,
                                               lan_command_type.LENGTH >> 8,
                                              *lan_command_type.DATA[:lan_command_type.LENGTH]])
        structure_lenght = 6 + lan_command_type.LENGTH
        request = string_at(byref(lan_command_type), structure_lenght)

        return bytes(request)

    def _parse_answer(self, buffer):
        """Расшифровка прочитанного пакета."""

        lan_command_type = cast(buffer, POINTER(LAN_COMMAND_TYPE)).contents
        xor = self._checksum([lan_command_type.VER,
                              lan_command_type.TYPE,
                              lan_command_type.ID,
                              lan_command_type.LENGTH & 0xFF,
                              lan_command_type.LENGTH >> 8,
                             *lan_command_type.DATA[:lan_command_type.LENGTH]])
        if xor != lan_command_type.XOR:
            msg = "Invalid message checksum"
            raise SMSDError(msg)

        return bytes(lan_command_type.DATA[:lan_command_type.LENGTH])

    def _execute(self, data, err_or_cmd, cmd_type, struct_type, *, write=False):
        """Выполнение команды и получение ответа."""

        buffer = string_at(byref(data), sizeof(data))

        request = self._make_request(cmd_type, sizeof(data), buffer)
        if answer := self._bus_exchange(request):
            ret_data = self._parse_answer(answer)
            structure = cast(ret_data, POINTER(struct_type)).contents
            if err_or_cmd is None:
                return deepcopy(structure)
            if err_or_cmd.value == structure.ERROR_OR_COMMAND:
                return write or structure.RETURN_DATA

            msg = f"{ERROR_OR_COMMAND(structure.ERROR_OR_COMMAND).name}"
            raise SMSDError(msg)

    def _password(self, command, err_or_cmd, password):
        """Посылка команды авторизации в устройство."""

        password = (c_ubyte * 8)(*bytearray(password, encoding="ascii")[:8]) \
                   if password else \
                   (c_ubyte * 8)(*(0xEF, 0xCD, 0xAB, 0x89, 0x67, 0x45, 0x23, 0x01))

        return self._execute(password, err_or_cmd, command,
                             COMMANDS_RETURN_DATA_TYPE,
                             write=True)

    def _config_or_stats(self, command, struct_type):
        """Посылка команды чтения настроек или статистики."""

        data = create_string_buffer(0)
        return self._execute(data, None, command, struct_type, write=False)

    def _powerstep01(self, command, err_or_cmd, value=0, *, write=False):
        """Посылка команды POWERSTEP01."""

        smsd_cmd_type = SMSD_CMD_TYPE()
        smsd_cmd_type.COMMAND = command.value
        smsd_cmd_type.DATA = value

        return self._execute(smsd_cmd_type, err_or_cmd,
                             CMD_TYPE.CODE_CMD_POWERSTEP01,
                             COMMANDS_RETURN_DATA_TYPE,
                             write=write)

    def _get_param(self, command, err_or_cmd):
        """Чтение значения параметра из устройства."""

        return self._powerstep01(command, err_or_cmd, 0, write=False)

    def _set_param(self, command, err_or_cmd, value=0):
        """Запись нового значения параметра в устройство."""

        return self._powerstep01(command, err_or_cmd, value, write=True)

    # Основные функции

    def get_version(self):
        """Получение версии протокола."""

        if answer := self._bus_exchange(b""):
            self.version = answer[1]
            return True

        msg = "Get protocol version error"
        raise SMSDError(msg)

    def authorization(self, password=None):
        """Авторизации пользователя с помощью пароля. Если пароль не задан, то
        используется пароль по умолчанию.
        """

        return self._password(CMD_TYPE.CODE_CMD_REQUEST,
                              ERROR_OR_COMMAND.OK_ACCESS,
                              password)

    def set_password(self, password=None):
        """Установка нового пароля для авторизации. Если новый пароль не задан,
        то устанавливается пароль по умолчанию.
        """

        return self._password(CMD_TYPE.CODE_CMD_PASSWORD_SET,
                              ERROR_OR_COMMAND.OK,
                              password)

    def get_lan_config(self):
        """Чтение текущих сетевых настроек."""

        lan_config = self._config_or_stats(CMD_TYPE.CODE_CMD_CONFIG_GET,
                                           SMSD_LAN_CONFIG_TYPE)
        return {"mac":  list(lan_config.MAC),
                "ip":   list(lan_config.IP),
                "sn":   list(lan_config.SN),
                "gw":   list(lan_config.GW),
                "dns":  list(lan_config.DNS),
                "port": lan_config.PORT,
                "dhcp": lan_config.DHCP}

    def set_lan_config(self, mac, ip, sn, gw, dns, port, dhcp):
        """Запись новых сетевых настроек."""

        lan_config = SMSD_LAN_CONFIG_TYPE()
        lan_config.MAC = (c_ubyte * 6)(*mac)
        lan_config.IP = (c_ubyte * 4)(*ip)
        lan_config.SN = (c_ubyte * 4)(*sn)
        lan_config.GW = (c_ubyte * 4)(*gw)
        lan_config.DNS = (c_ubyte * 4)(*dns)
        lan_config.PORT = port
        lan_config.DHCP = dhcp

        return self._execute(lan_config, ERROR_OR_COMMAND.OK,
                             CMD_TYPE.CODE_CMD_CONFIG_SET,
                             COMMANDS_RETURN_DATA_TYPE,
                             write=True)

    def get_error_statistics(self):
        """Чтения из памяти контроллера информации о количестве включений
        рабочего режима контроллера и статистики по ошибкам.
        """

        stats = self._config_or_stats(CMD_TYPE.CODE_CMD_ERROR_GET,
                                      LAN_ERROR_STATISTICS)
        return {"n_starts":                  stats.N_STARTS,
                "error_xt":                  stats.ERROR_XT,
                "error_time_out":            stats.ERROR_TIME_OUT,
                "error_init_powerstep01":    stats.ERROR_INIT_POWERSTEP01,
                "error_init_wiznet":         stats.ERROR_INIT_WIZNET,
                "error_init_fram":           stats.ERROR_INIT_FRAM,
                "error_socket":              stats.ERROR_SOCKET,
                "error_fram":                stats.ERROR_FRAM,
                "error_interrupt":           stats.ERROR_INTERRUPT,
                "error_extern_5v":           stats.ERROR_EXTERN_5V,
                "error_extern_vdd":          stats.ERROR_EXTERN_VDD,
                "error_thermal_powerstep01": stats.ERROR_THERMAL_POWERSTEP01,
                "error_thermal_brake":       stats.ERROR_THERMAL_BRAKE,
                "error_command_powerstep01": stats.ERROR_COMMAND_POWERSTEP01,
                "error_uvlo_powerstep01":    stats.ERROR_UVLO_POWERSTEP01,
                "error_stall_powerstep01":   stats.ERROR_STALL_POWERSTEP01,
                "error_work_program":        stats.ERROR_WORK_PROGRAM}

    def get_max_speed(self):
        """Чтение текущего значения установленной максимальной скорости."""

        return self._get_param(COMMAND.CMD_POWERSTEP01_GET_MAX_SPEED,
                               ERROR_OR_COMMAND.COMMAND_GET_MAX_SPEED)

    def set_max_speed(self, speed):
        """Установка максимальной скорости шагового двигателя."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SET_MAX_SPEED,
                               ERROR_OR_COMMAND.OK,
                               speed)

    def get_min_speed(self):
        """Чтение текущего значения установленной минимальной скорости."""

        return self._get_param(COMMAND.CMD_POWERSTEP01_GET_MIN_SPEED,
                               ERROR_OR_COMMAND.COMMAND_GET_MIN_SPEED)

    def set_min_speed(self, speed):
        """Установка минимальной скорости вращения двигателя."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SET_MIN_SPEED,
                               ERROR_OR_COMMAND.OK,
                               speed)

    def get_speed(self):
        """Чтение текущего значения скорости."""

        return self._get_param(COMMAND.CMD_POWERSTEP01_GET_SPEED,
                               ERROR_OR_COMMAND.COMMAND_GET_SPEED)

    def run_f(self, speed):
        """Старт непрерывного вращения двигателя в прямом направлении на
        указанной скорости.
        """

        return self._set_param(COMMAND.CMD_POWERSTEP01_RUN_F,
                               ERROR_OR_COMMAND.OK,
                               speed)

    def run_r(self, speed):
        """Старт непрерывного вращения двигателя в обратном направлении на
        указанной скорости.
        """

        return self._set_param(COMMAND.CMD_POWERSTEP01_RUN_R,
                               ERROR_OR_COMMAND.OK,
                               speed)

    def get_mode(self):
        """Чтение настроек управления двигателем."""

        result = self._get_param(COMMAND.CMD_POWERSTEP01_GET_MODE,
                                 ERROR_OR_COMMAND.COMMAND_GET_MODE)
        return {"current_or_voltage": result >> 0 & 0x1,
                "motor_type":         result >> 1 & 0x3F,
                "microstepping":      result >> 7 & 0x7,
                "work_current":       result >> 10 & 0x7F,
                "stop_current":       result >> 17 & 0x3,
                "program_n":          result >> 19 & 0x3}

    def set_mode(self, current_or_voltage, motor_type, microstepping,
                       work_current, stop_current):
        """Установка параметров управления двигателем."""

        value = (stop_current << 17) | (work_current << 10) | \
                (microstepping << 7) | (motor_type << 1) | current_or_voltage

        return self._set_param(COMMAND.CMD_POWERSTEP01_SET_MODE,
                               ERROR_OR_COMMAND.OK,
                               value)

    def set_acc(self, acceleration):
        """Установка значения ускорения двигателя."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SET_ACC,
                               ERROR_OR_COMMAND.OK,
                               acceleration)

    def set_dec(self, deceleration):
        """Установка значения замедления шагового двигателя."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SET_DEC,
                               ERROR_OR_COMMAND.OK,
                               deceleration)

    def move_f(self, steps):
        """Перемещение двигателя в прямом направлении на указанную величину."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_MOVE_F,
                               ERROR_OR_COMMAND.OK,
                               steps)

    def move_r(self, steps):
        """Перемещение двигателя в обратном направлении на указанную величину."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_MOVE_R,
                               ERROR_OR_COMMAND.OK,
                               steps)

    def get_abs_pos(self):
        """Чтение положения двигателя."""

        return self._get_param(COMMAND.CMD_POWERSTEP01_GET_ABS_POS,
                               ERROR_OR_COMMAND.COMMAND_GET_ABS_POS)

    def get_el_pos(self):
        """Чтение электрического положения ротора двигателя."""

        return self._get_param(COMMAND.CMD_POWERSTEP01_GET_EL_POS,
                               ERROR_OR_COMMAND.COMMAND_GET_EL_POS)

    def get_status_and_clr(self):
        """Чтение текущего статуса контроллера и сброса всех флагов ошибок."""

        return self._get_param(COMMAND.CMD_POWERSTEP01_GET_STATUS_AND_CLR,
                               ERROR_OR_COMMAND.OK)

    def get_status_in_event(self):
        """Чтение текущего состояния входных сигналов."""

        result = self._get_param(COMMAND.CMD_POWERSTEP01_STATUS_IN_EVENT,
                                 ERROR_OR_COMMAND.COMMAND_GET_STATUS_IN_EVENT)
        return {"Int_0": result >> 0 & 1, "Mask_0": result >> 8 & 1,  "Wait_0": result >> 16 & 1,
                "Int_1": result >> 1 & 1, "Mask_1": result >> 9 & 1,  "Wait_1": result >> 17 & 1,
                "Int_2": result >> 2 & 1, "Mask_2": result >> 10 & 1, "Wait_2": result >> 18 & 1,
                "Int_3": result >> 3 & 1, "Mask_3": result >> 11 & 1, "Wait_3": result >> 19 & 1,
                "Int_4": result >> 4 & 1, "Mask_4": result >> 12 & 1, "Wait_4": result >> 20 & 1,
                "Int_5": result >> 5 & 1, "Mask_5": result >> 13 & 1, "Wait_5": result >> 21 & 1,
                "Int_6": result >> 6 & 1, "Mask_6": result >> 14 & 1, "Wait_6": result >> 22 & 1,
                "Int_7": result >> 7 & 1, "Mask_7": result >> 15 & 1, "Wait_7": result >> 23 & 1}

    def go_to_f(self, position):
        """Перемещение в заданную позицию в прямом направлении."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_GO_TO_F,
                               ERROR_OR_COMMAND.OK,
                               position)

    def go_to_r(self, position):
        """Перемещение в заданную позицию в обратном направлении."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_GO_TO_R,
                               ERROR_OR_COMMAND.OK,
                               position)

    def set_mask_event(self, mask):
        """Маскирование входных сигналов."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SET_MASK_EVENT,
                               ERROR_OR_COMMAND.OK,
                               mask)

    def go_until_f(self, signal):
        """Старт вращения двигателя в прямом направлении на максимальной
        скорости до получения сигнала на вход.
        """

        return self._set_param(COMMAND.CMD_POWERSTEP01_GO_UNTIL_F,
                               ERROR_OR_COMMAND.OK,
                               signal)

    def go_until_r(self, signal):
        """Старт вращения двигателя в обратном направлении на максимальной
        скорости до получения сигнала на вход.
        """

        return self._set_param(COMMAND.CMD_POWERSTEP01_GO_UNTIL_R,
                               ERROR_OR_COMMAND.OK,
                               signal)

    def end(self):
        """Обозначение конца программы."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_END,
                               ERROR_OR_COMMAND.END_PROGRAMS)

    def scan_zero_f(self, speed):
        """Поиск нулевого положения в прямом направлении с заданной скоростью."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SCAN_ZERO_F,
                               ERROR_OR_COMMAND.OK,
                               speed)

    def scan_zero_r(self, speed):
        """Поиск нулевого положения в обратном направлении с заданной скоростью."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SCAN_ZERO_R,
                               ERROR_OR_COMMAND.OK,
                               speed)

    def scan_label_f(self, speed):
        """Поиск метки положения в прямом направлении."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SCAN_LABEL_F,
                               ERROR_OR_COMMAND.OK,
                               speed)

    def scan_label_r(self, speed):
        """Поиск метки положения в обратном направлении."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SCAN_LABEL_R,
                               ERROR_OR_COMMAND.OK,
                               speed)

    def go_zero(self):
        """Перемещение в нулевое положение."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_GO_ZERO,
                               ERROR_OR_COMMAND.OK)

    def go_label(self):
        """Перемещение в положение, которое было отмечено как метка."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_GO_LABEL,
                               ERROR_OR_COMMAND.OK)

    def go_to(self, position):
        """Перемещение в заданное положение по кратчайшему пути."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_GO_TO,
                               ERROR_OR_COMMAND.OK,
                               position)

    def reset_pos(self):
        """Обнуление счетчика текущего положения."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_RESET_POS,
                               ERROR_OR_COMMAND.OK)

    def reset_powerstep01(self):
        """Полный аппаратный и программный сброс модуля управления шаговым
        двигателем, но не контроллера в целом.
        """

        return self._set_param(COMMAND.CMD_POWERSTEP01_RESET_POWERSTEP01,
                               ERROR_OR_COMMAND.OK)

    def soft_stop(self):
        """Плавная остановка двигателя с заданным ускорением."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SOFT_STOP,
                               ERROR_OR_COMMAND.OK)

    def hard_stop(self):
        """Резкая остановка шагового двигателя."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_HARD_STOP,
                               ERROR_OR_COMMAND.OK)

    def soft_hi_z(self):
        """Плавная остановка шагового двигателя с заданным ускорением."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SOFT_HI_Z,
                               ERROR_OR_COMMAND.OK)

    def hard_hi_z(self):
        """Резкая остановка и обесточивания обмоток двигателя."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_HARD_HI_Z,
                               ERROR_OR_COMMAND.OK)

    def set_fs_speed(self, speed):
        """Установка скорости перехода на полношаговый режим работы."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SET_FS_SPEED,
                               ERROR_OR_COMMAND.OK,
                               speed)

    def set_wait(self, time):
        """Задание паузы."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SET_WAIT,
                               ERROR_OR_COMMAND.OK,
                               time)

    def set_rele(self):
        """Включение реле контроллера."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SET_RELE,
                               ERROR_OR_COMMAND.STATUS_RELE_SET)

    def clr_rele(self):
        """Выключение реле контроллера."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_CLR_RELE,
                               ERROR_OR_COMMAND.STATUS_RELE_CLR)

    def get_rele(self):
        """Запрос состояния реле контроллера."""

        try:
            self._get_param(COMMAND.CMD_POWERSTEP01_GET_RELE,
                            ERROR_OR_COMMAND.OK)
        except SMSDError as err:
            if str(err) == "STATUS_RELE_CLR":
                return 0
            if str(err) == "STATUS_RELE_SET":
                return 1
            raise

    def wait_in0(self):
        """Ожидание поступления сигнала на вход IN0."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_WAIT_IN0,
                               ERROR_OR_COMMAND.OK)

    def wait_in1(self):
        """Ожидание поступления сигнала на вход IN1."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_WAIT_IN1,
                               ERROR_OR_COMMAND.OK)

    def step_clock(self):
        """Изменение режима управления двигателем на импульсное сигналами
        EN, STEP, DIR.
        """

        return self._set_param(COMMAND.CMD_POWERSTEP01_STEP_CLOCK,
                               ERROR_OR_COMMAND.OK)

    def stop_usb(self):
        """Остановка работы микросхемы USB."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_STOP_USB,
                               ERROR_OR_COMMAND.END_PROGRAMS)

    def get_stack(self):
        """Чтение информации о выполняемой в данный момент программе."""

        result = self._get_param(COMMAND.CMD_POWERSTEP01_GET_STACK,
                                 ERROR_OR_COMMAND.COMMAND_GET_STACK)
        return {"command": result & 0xFF,
                "program": result >> 8 & 0x3}

    def wait_continue(self):
        """Ожидание прихода синхросигнала на вход CONTINUE."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_WAIT_CONTINUE,
                               ERROR_OR_COMMAND.OK)

    def set_wait_2(self, time):
        """Задание паузы (может быть прервано поступлением сигнала на вход
        IN0, IN1 или SET_ZERO).
        """

        return self._set_param(COMMAND.CMD_POWERSTEP01_SET_WAIT_2,
                               ERROR_OR_COMMAND.OK,
                               time)

    def scan_mark2_f(self, speed):
        """Поиск метки положения в прямом направлении."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SCAN_MARK2_F,
                               ERROR_OR_COMMAND.OK,
                               speed)

    def scan_mark2_r(self, speed):
        """Поиск метки положения в обратном направлении."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_SCAN_MARK2_R,
                               ERROR_OR_COMMAND.OK,
                               speed)

    def goto_program_if_zero(self, program, command):
        """Переход к заданной команде заданной программы, если значение
        текущей позиции равно 0.
        """

        return self._set_param(COMMAND.CMD_POWERSTEP01_GOTO_PROGRAM_IF_ZERO,
                               ERROR_OR_COMMAND.OK,
                               program << 8 | command)

    def goto_program_if_in_zero(self, program, command):
        """Переход к заданной команде заданной программы, если на входе
        SET_ZERO присутствует сигнал.
        """

        return self._set_param(COMMAND.CMD_POWERSTEP01_GOTO_PROGRAM_IF_IN_ZERO,
                               ERROR_OR_COMMAND.OK,
                               program << 8 | command)

    def stop_program_mem(self):
        """Остановка выполнения программы."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_STOP_PROGRAM_MEM,
                               ERROR_OR_COMMAND.OK)

    def start_program_mem0(self):
        """Старт программы, записанной в область памяти 0 контроллера."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_START_PROGRAM_MEM0,
                               ERROR_OR_COMMAND.OK)

    def start_program_mem1(self):
        """Старт программы, записанной в область памяти 1 контроллера."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_START_PROGRAM_MEM1,
                               ERROR_OR_COMMAND.OK)

    def start_program_mem2(self):
        """Старт программы, записанной в область памяти 2 контроллера."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_START_PROGRAM_MEM2,
                               ERROR_OR_COMMAND.OK)

    def start_program_mem3(self):
        """Старт программы, записанной в область памяти 3 контроллера."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_START_PROGRAM_MEM3,
                               ERROR_OR_COMMAND.OK)

    def goto_program(self, program, command):
        """Безусловный переход к заданной команде заданной программы."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_GOTO_PROGRAM,
                               ERROR_OR_COMMAND.OK,
                               program << 8 | command)

    def goto_program_if_in0(self, program, command):
        """Переход к заданной команде заданной программы, если на входе IN0
        присутствует сигнал.
        """

        return self._set_param(COMMAND.CMD_POWERSTEP01_GOTO_PROGRAM_IF_IN0,
                               ERROR_OR_COMMAND.OK,
                               program << 8 | command)

    def goto_program_if_in1(self, program, command):
        """Переход к заданной команде заданной программы, если на входе IN1
        присутствует сигнал.
        """

        return self._set_param(COMMAND.CMD_POWERSTEP01_GOTO_PROGRAM_IF_IN1,
                               ERROR_OR_COMMAND.OK,
                               program << 8 | command)

    def call_program(self, program, command):
        """Вызов подпрограммы."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_CALL_PROGRAM,
                               ERROR_OR_COMMAND.OK,
                               program << 8 | command)

    def return_program(self):
        """Возврат из подпрограммы в основную программу."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_RETURN_PROGRAM,
                               ERROR_OR_COMMAND.OK)

    def loop_program(self, cycles, commands):
        """Контроллер повторяет заданное число раз заданное количество команд."""

        return self._set_param(COMMAND.CMD_POWERSTEP01_LOOP_PROGRAM,
                               ERROR_OR_COMMAND.OK,
                               cycles << 10 | commands)


__all__ = ["Smsd"]
