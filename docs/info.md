<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

This project is a 16-bit circular CORDIC engine that computes sine and cosine of an input angle, controlled over SPI.

- **SPI target:** Mode 0 (CPOL=0, CPHA=0), 16-bit words, MSB first. The chip is the SPI target and the host is the controller. SS_N, SCK and MOSI are synchronized to the system clock internally, so SCK does not need to be related to the system clock as long as it is slow enough (see below).
- **Angle format:** signed 16-bit two's complement, -180 to just under +180 degrees (angle in degrees = raw / 32768 x 180). For example, 0x4000 = 90 degrees.
- **Result format:** signed 16-bit Q1.15 (value = raw / 32768).
- **Frame protocol:** each chip-select frame carries 16-bit words.
  - Word 0: the host sends an angle on MOSI. Every word 0 starts a new calculation (so a dummy 0x0000 starts one for angle 0). MISO returns the cosine of the previous calculation, which is latched when SS_N goes low.
  - Word 1: the host sends a dummy word (0x0000). MISO returns the sine of the calculation started by word 0.
  - To read the cosine of that calculation, run a second frame: its word 0 returns the cosine on MISO (and starts a new calculation for whatever angle that word carries).
  - Frames longer than two words keep alternating: even words start a calculation and return the cosine, odd words return the sine.
  - The result registers always hold the most recent calculation, including ones started by dummy words.
- **Done flag:** `uo[1]` is the CORDIC done output and indicates that a calculation has finished and its sine and cosine results are valid.
- **SPI clock limit:** the system clock must be at least about 6 times faster than SCK, so with a 10 MHz clock keep SCK below about 1.6 MHz. The sine word is loaded at the start of word 1, so the CORDIC must also finish within half an SCK period after word 0 ends; the testbench uses about 200 kHz, which satisfies this.

The design is made of three modules: `spi_target` (SPI shift register and word handshake), `cordic_circular` (iterative shift-add CORDIC in rotation mode) and `cordic_top` (frame/word sequencing between the two).

## How to test

1. Apply a clock (up to 10 MHz) and pulse `rst_n` low, then high.
2. Keep SS_N high (idle) and SCK low.
3. Frame 1: pull SS_N low, send the 16-bit angle, then 0x0000. The second word read back on MISO is the sine.
4. Release SS_N, then do a second frame with one 0x0000 word. The word read back on MISO is the cosine.
5. Convert both results from signed Q1.15 to a decimal value (divide by 32768) and compare with sin/cos of the angle.

The cocotb testbench in `test/` does this at a 10 MHz clock and about 200 kHz SPI clock. It checks cardinal angles, boundary angles, 100 random angles (tolerance 0.002) and recovery from a reset in the middle of a calculation.

| Pin    | Function     |
|--------|--------------|
| ui[0]  | SPI SS_N     |
| ui[1]  | SPI SCK      |
| ui[2]  | SPI MOSI     |
| uo[0]  | SPI MISO     |
| uo[1]  | CORDIC done  |

## External hardware

A SPI controller is needed, such as a microcontroller (an RP2040 was used for development) or a USB-SPI adapter. No other external hardware is required.
