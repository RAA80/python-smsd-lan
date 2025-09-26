#! /usr/bin/env python3

"""Проверка работы всех функций."""

import logging
from time import sleep

from smsd.client import SmsdTcpClient, SmsdUsbClient
from smsd.protocol import COMMAND, MEMORY_BANK, MODE, SMSD_LAN_CONFIG_TYPE

logging.basicConfig(level=logging.INFO)


if __name__ == "__main__":
    client = SmsdTcpClient(address="192.168.1.2:5000", timeout=1.0)
    # client = SmsdUsbClient(address="COM7", timeout=1.0)

    print(f"protocol version: {client._version}")

    # sleep(2)  # Без паузы при работе через USB при первом включении возвращается ошибка ERROR_ACCESS_TIMEOUT

    print(f"authorization: {client.authorization()}")
    # print(f"set_password: {client.set_password('12345678')}")

    # lan = SMSD_LAN_CONFIG_TYPE()
    # lan.MAC = (0x00, 0xf8, 0xdc, 0x3f, 0x00, 0x00)
    # lan.IP = (192, 168, 1, 2)
    # lan.SN = (255, 255, 0, 0)
    # lan.GW = (192, 168, 1, 1)
    # lan.DNS = (0, 0, 0, 0)
    # lan.PORT = 5000
    # lan.DHCP = 1
    # print(f"set_lan_config: {client.set_lan_config(lan)}")

    lan = client.get_lan_config()
    print(f"get_lan_config: {lan}")
    print(f"    mac: {tuple(lan.MAC)}")
    print(f"    ip: {tuple(lan.IP)}")
    print(f"    sn: {tuple(lan.SN)}")
    print(f"    gw: {tuple(lan.GW)}")
    print(f"    dns: {tuple(lan.DNS)}")
    print(f"    port: {lan.PORT}")
    print(f"    dhcp: {lan.DHCP}")

    stats = client.get_error_statistics()
    print(f"get_error_statistics: {stats}")
    print(f"    n_starts: {stats.N_STARTS}")
    print(f"    error_xt: {stats.ERROR_XT}")
    print(f"    error_time_out: {stats.ERROR_TIME_OUT}")
    print(f"    error_init_powerstep01: {stats.ERROR_INIT_POWERSTEP01}")
    print(f"    error_init_wiznet: {stats.ERROR_INIT_WIZNET}")
    print(f"    error_init_fram: {stats.ERROR_INIT_FRAM}")
    print(f"    error_socket: {stats.ERROR_SOCKET}")
    print(f"    error_fram: {stats.ERROR_FRAM}")
    print(f"    error_interrupt: {stats.ERROR_INTERRUPT}")
    print(f"    error_extern_5v: {stats.ERROR_EXTERN_5V}")
    print(f"    error_extern_vdd: {stats.ERROR_EXTERN_VDD}")
    print(f"    error_thermal_powerstep01: {stats.ERROR_THERMAL_POWERSTEP01}")
    print(f"    error_thermal_brake: {stats.ERROR_THERMAL_BRAKE}")
    print(f"    error_command_powerstep01: {stats.ERROR_COMMAND_POWERSTEP01}")
    print(f"    error_uvlo_powerstep01: {stats.ERROR_UVLO_POWERSTEP01}")
    print(f"    error_stall_powerstep01: {stats.ERROR_STALL_POWERSTEP01}")
    print(f"    error_work_program: {stats.ERROR_WORK_PROGRAM}")

    print(f"get_speed: {client.get_speed()}")

    print(f"set_max_speed: {client.set_max_speed(200)}")
    print(f"get_max_speed: {client.get_max_speed()}")

    print(f"set_min_speed: {client.set_min_speed(70)}")
    print(f"get_min_speed: {client.get_min_speed()}")

    print(f"set_acc: {client.set_acc(20)}")
    print(f"set_dec: {client.set_dec(20)}")

    mode = MODE()
    mode.CURRENT_OR_VOLTAGE = 1
    mode.MOTOR_TYPE = 30
    mode.MICROSTEPPING = 4
    mode.WORK_CURRENT = 10
    mode.STOP_CURRENT = 0
    mode.PROGRAM_N = 0
    print(f"set_mode: {client.set_mode(mode)}")

    mode = client.get_mode()
    print(f"get_mode: {mode}")
    print(f"    current_or_voltage: {mode.CURRENT_OR_VOLTAGE}")
    print(f"    motor_type: {mode.MOTOR_TYPE}")
    print(f"    microstepping: {mode.MICROSTEPPING}")
    print(f"    work_current: {mode.WORK_CURRENT}")
    print(f"    stop_current: {mode.STOP_CURRENT}")
    print(f"    program_n: {mode.PROGRAM_N}")

    # print(f"run_f: {client.run_f(500)}")
    # sleep(5)
    # print(f"run_f: {client.run_r(500)}")
    # sleep(5)

    print(f"status_powerstep01: {client.status_powerstep01}")   # Обновляется после каждого вызова команды CMD_PowerSTEP01_xxx
    print(f"    HIZ: {client.status_powerstep01.HIZ}")
    print(f"    BUSY: {client.status_powerstep01.BUSY}")
    print(f"    SW_F: {client.status_powerstep01.SW_F}")
    print(f"    SW_EVN: {client.status_powerstep01.SW_EVN}")
    print(f"    DIR: {client.status_powerstep01.DIR}")
    print(f"    MOT_STATUS: {client.status_powerstep01.MOT_STATUS}")
    print(f"    CMD_ERROR: {client.status_powerstep01.CMD_ERROR}")
    print(f"    RESERVE: {client.status_powerstep01.RESERVE}")

    print(f"move_f: {client.move_f(5000)}")
    sleep(5)
    print(f"move_r: {client.move_r(5000)}")
    sleep(5)

    # print(f"go_to_f: {client.go_to_f(500)}")
    # sleep(5)
    # print(f"go_to_r: {client.go_to_r(0)}")
    # sleep(5)

    # print(f"go_until_f: {client.go_until_f(0)}")
    # sleep(5)
    # print(f"go_until_r: {client.go_until_r(0)}")
    # sleep(5)

    # print(f"scan_zero_f: {client.scan_zero_f(500)}")
    # sleep(5)
    # print(f"scan_zero_r: {client.scan_zero_r(500)}")
    # sleep(5)

    # print(f"scan_label_f: {client.scan_label_f(500)}")
    # sleep(5)
    # print(f"scan_label_r: {client.scan_label_r(500)}")
    # sleep(5)

    # print(f"scan_mark_f: {client.scan_mark2_f(500)}")
    # sleep(5)
    # print(f"scan_mark_r: {client.scan_mark2_r(500)}")
    # sleep(5)

    # print(f"go_zero: {client.go_zero()}")
    # sleep(5)

    # print(f"go_label: {client.go_label()}")
    # sleep(5)

    # print(f"go_label: {client.go_to(1000)}")
    # sleep(5)

    print(f"get_abs_pos: {client.get_abs_pos()}")
    print(f"get_el_pos: {client.get_el_pos()}")

    print(f"get_status_and_clr: {client.get_status_and_clr()}")

    print(f"set_mask_event: {client.set_mask_event(0)}")
    status = client.get_status_in_event()
    print(f"get_status_in_event: {status}")
    print(f"    Int_0: {status.INT_0}")
    print(f"    Int_1: {status.INT_1}")
    print(f"    Int_2: {status.INT_2}")
    print(f"    Int_3: {status.INT_3}")
    print(f"    Int_4: {status.INT_4}")
    print(f"    Int_5: {status.INT_5}")
    print(f"    Int_6: {status.INT_6}")
    print(f"    Int_7: {status.INT_7}")
    print(f"    Mask_0: {status.MASK_0}")
    print(f"    Mask_1: {status.MASK_1}")
    print(f"    Mask_2: {status.MASK_2}")
    print(f"    Mask_3: {status.MASK_3}")
    print(f"    Mask_4: {status.MASK_4}")
    print(f"    Mask_5: {status.MASK_5}")
    print(f"    Mask_6: {status.MASK_6}")
    print(f"    Mask_7: {status.MASK_7}")
    print(f"    Wait_0: {status.WAIT_0}")
    print(f"    Wait_1: {status.WAIT_1}")
    print(f"    Wait_2: {status.WAIT_2}")
    print(f"    Wait_3: {status.WAIT_3}")
    print(f"    Wait_4: {status.WAIT_4}")
    print(f"    Wait_5: {status.WAIT_5}")
    print(f"    Wait_6: {status.WAIT_6}")
    print(f"    Wait_7: {status.WAIT_7}")

    print(f"soft_stop: {client.soft_stop()}")
    print(f"hard_stop: {client.hard_stop()}")

    print(f"soft_hi_z: {client.soft_hi_z()}")
    print(f"hard_hi_z: {client.hard_hi_z()}")

    print(f"set_fs_speed: {client.set_fs_speed(10000)}")
    print(f"set_wait: {client.set_wait(0)}")
    print(f"set_wait_2: {client.set_wait_2(0)}")

    print(f"set_rele: {client.set_rele()}")
    print(f"clr_rele: {client.clr_rele()}")
    print(f"get_rele: {client.get_rele()}")

    # memory0 = client.read_memory0()
    # print(f"read_memory0: {memory0.data[0].COMMAND}, {memory0.data[0].DATA}")
    # print(f"read_memory0: {memory0.data[1].COMMAND}, {memory0.data[1].DATA}")

    # print(f"read_memory1: {client.read_memory1()}")
    # print(f"read_memory2: {client.read_memory2()}")
    # print(f"read_memory3: {client.read_memory3()}")

    # memory1 = MEMORY_BANK()
    # memory1.data[0].COMMAND = COMMAND.CMD_POWERSTEP01_SET_MIN_SPEED
    # memory1.data[0].DATA = 300
    # memory1.data[1].COMMAND = COMMAND.CMD_POWERSTEP01_SET_MAX_SPEED
    # memory1.data[1].DATA = 800
    # print(f"write_memory1: {client.write_memory1(memory1)}")

    # print(f"write_memory0: {client.write_memory0(memory1)}")
    # print(f"write_memory2: {client.write_memory2(memory1)}")
    # print(f"write_memory3: {client.write_memory3(memory1)}")

    # print(f"start_program_mem0: {client.start_program_mem0()}")
    # print(f"start_program_mem1: {client.start_program_mem1()}")
    # print(f"start_program_mem2: {client.start_program_mem2()}")
    # print(f"start_program_mem3: {client.start_program_mem3()}")
    # print(f"stop_program_mem: {client.stop_program_mem()}")

    # print(f"goto_program_if_zero: {client.goto_program_if_zero(0, 0)}")
    # print(f"goto_program_if_in_zero: {client.goto_program_if_in_zero(0, 0)}")
    # print(f"goto_program: {client.goto_program(0, 0)}")
    # print(f"goto_program_if_in0: {client.goto_program_if_in0(0, 0)}")
    # print(f"goto_program_if_in1: {client.goto_program_if_in1(0, 0)}")
    # print(f"call_program: {client.call_program(0, 0)}")
    # print(f"loop_program: {client.loop_program(0, 0)}")
    # print(f"return_program: {client.return_program()}")

    print(f"get_stack: {client.get_stack()}")
    print(f"wait_continue: {client.wait_continue()}")

    print(f"wait_in0: {client.wait_in0()}")
    print(f"wait_in1: {client.wait_in1()}")

    print(f"step_clock: {client.step_clock()}")

    print(f"reset_pos: {client.reset_pos()}")
    print(f"reset_powerstep01: {client.reset_powerstep01()}")

    print(f"end: {client.end()}")
    print(f"stop_usb: {client.stop_usb()}")
