# SPDX-FileCopyrightText: © 2026 Yash
# SPDX-License-Identifier: Apache-2.0

import math
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, Timer

TOLERANCE = 0.002
N_SWEEP = 100  # drop to 50 if the gate-level run is too slow


def to_signed16(val: int) -> int:
    """Converts an unsigned 16-bit word to a signed 16-bit integer."""
    val = val & 0xFFFF
    return val - 65536 if val >= 32768 else val


class Pins:
    """Drives ui_in[2:0] = {mosi, sck, ss_n} and reads uo_out[1:0] = {done, miso}."""

    def __init__(self, dut):
        self.dut = dut
        self.ss_n = 1
        self.sck = 0
        self.mosi = 0
        self.drive()

    def drive(self):
        self.dut.ui_in.value = (self.mosi << 2) | (self.sck << 1) | self.ss_n

    @property
    def miso(self) -> int:
        return int(self.dut.uo_out.value) & 1

    @property
    def done(self) -> int:
        return (int(self.dut.uo_out.value) >> 1) & 1


async def start_clock(dut):
    # 10 MHz, matches the ASIC max clock
    cocotb.start_soon(Clock(dut.clk, 100, unit="ns").start())


async def reset_dut(dut, pins):
    dut.ena.value = 1
    dut.uio_in.value = 0
    pins.ss_n, pins.sck, pins.mosi = 1, 0, 0
    pins.drive()
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)


async def spi_xfer(pins, tx_word: int, sck_half_ns: int = 2400) -> int:
    """16-bit SPI Mode 0, MSB first. MOSI changes while SCK low, MISO sampled on rising edge."""
    rx_word = 0
    for b in range(15, -1, -1):
        pins.mosi = (tx_word >> b) & 1
        pins.drive()
        await Timer(sck_half_ns, unit="ns")

        pins.sck = 1
        pins.drive()
        rx_word = (rx_word << 1) | pins.miso
        await Timer(sck_half_ns, unit="ns")

        pins.sck = 0
        pins.drive()
    return rx_word


async def run_cordic_transaction(pins, angle_raw: int, sck_half_ns: int = 2400, cs_delay_ns: int = 100):
    """
    Frame 0: word0 MOSI=angle, word1 MOSI=0 -> MISO word1 = SIN
    Frame 1: word0 MOSI=0                   -> MISO word0 = COS
    """
    pins.ss_n = 0
    pins.drive()
    await Timer(cs_delay_ns, unit="ns")
    _ = await spi_xfer(pins, angle_raw, sck_half_ns)
    w1_rx = await spi_xfer(pins, 0x0000, sck_half_ns)
    await Timer(cs_delay_ns, unit="ns")
    pins.ss_n = 1
    pins.drive()
    await Timer(cs_delay_ns, unit="ns")

    pins.ss_n = 0
    pins.drive()
    await Timer(cs_delay_ns, unit="ns")
    cos_rx = await spi_xfer(pins, 0x0000, sck_half_ns)
    await Timer(cs_delay_ns, unit="ns")
    pins.ss_n = 1
    pins.drive()
    await Timer(cs_delay_ns, unit="ns")

    act_sin = to_signed16(w1_rx) / 32768.0
    act_cos = to_signed16(cos_rx) / 32768.0

    deg = (to_signed16(angle_raw) / 32768.0) * 180.0
    rad = math.radians(deg)
    exp_cos, exp_sin = math.cos(rad), math.sin(rad)

    return (deg, act_cos, exp_cos, abs(act_cos - exp_cos),
            act_sin, exp_sin, abs(act_sin - exp_sin))


@cocotb.test()
async def test_cardinal_and_boundary_angles(dut):
    """Cardinal angles and precision limits"""
    await start_clock(dut)
    pins = Pins(dut)
    await reset_dut(dut, pins)

    # 0, 90, -90, ~180, -180, +1 LSB, -1 LSB, plus a few in-between
    test_angles = [0, 16384, -16384, 32767, -32768, 1, -1, 8192, -8192, 24576, -24576]

    for raw_ang in test_angles:
        deg, act_c, exp_c, err_c, act_s, exp_s, err_s = await run_cordic_transaction(pins, raw_ang & 0xFFFF)
        dut._log.info(f"ANG {deg:7.2f} | COS act={act_c:8.5f} exp={exp_c:8.5f} | SIN act={act_s:8.5f} exp={exp_s:8.5f}")
        assert err_c <= TOLERANCE, f"COS error ({err_c:.5f}) out of spec at {deg} deg"
        assert err_s <= TOLERANCE, f"SIN error ({err_s:.5f}) out of spec at {deg} deg"


@cocotb.test()
async def test_random_angle_sweep(dut):
    """Randomized angle sweep"""
    await start_clock(dut)
    pins = Pins(dut)
    await reset_dut(dut, pins)

    random.seed(1234)
    max_err_c = max_err_s = 0.0

    for i in range(N_SWEEP):
        rand_ang = random.randint(-32768, 32767) & 0xFFFF
        deg, _, _, err_c, _, _, err_s = await run_cordic_transaction(pins, rand_ang)
        max_err_c = max(max_err_c, err_c)
        max_err_s = max(max_err_s, err_s)
        assert err_c <= TOLERANCE and err_s <= TOLERANCE, f"Iteration {i} failed at {deg} deg"

    dut._log.info(f"SWEEP DONE | max COS err = {max_err_c:.6f} | max SIN err = {max_err_s:.6f}")


@cocotb.test()
async def test_mid_calculation_reset(dut):
    """Assert reset while the CORDIC is mid-calculation, then check recovery"""
    await start_clock(dut)
    pins = Pins(dut)
    await reset_dut(dut, pins)

    pins.ss_n = 0
    pins.drive()
    _ = await spi_xfer(pins, 16384, sck_half_ns=1000)

    await Timer(500, unit="ns")
    dut.rst_n.value = 0
    await Timer(300, unit="ns")
    dut.rst_n.value = 1
    pins.ss_n = 1
    pins.drive()
    await Timer(500, unit="ns")

    _, _, _, err_c, _, _, err_s = await run_cordic_transaction(pins, 0)
    assert err_c <= TOLERANCE and err_s <= TOLERANCE, "Failed to recover after mid-calculation reset"
