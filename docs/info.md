<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

This project is a 16-bit circular CORDIC engine that computes sine and cosine of an input angle, controlled over SPI.

- **SPI target:** Mode 0 (CPOL=0, CPHA=0), 16-bit words, MSB first. The chip is the SPI target and the host is the controller.
- **Angle format:** signed 16-bit two's complement, where the full range maps to -180 to +180 degrees (angle in degrees = raw / 32768 x 180). For example, 0x4000 = 90 degrees.
- **Result format:** signed 16-bit Q1.15 (value = raw / 32768).
- **Frame protocol:** each chip-select frame carries 16-bit words.
  - Word 0: the host sends the angle on MOSI, which starts the CORDIC. MISO returns the cosine of the previous calculation.
  - Word 1: the host sends a dummy word (0x0000). MISO returns the sine of the current calculation.
  - A second frame (dummy word) reads back the cosine of the current calculation.
- **Done flag:** `uo[1]` indicates that the CORDIC has finished a calculation.

The design is made of three modules: `spi_target` (SPI shift register and word handshake), `cordic_circular` (iterative shift-add CORDIC in rotation mode) and `cordic_top` (frame/word sequencing between the two).

## How to test

1. Run it and pulse `rst_n` low, then high.
2. Keep SS_N high (idle) and SCK low.
3. Frame 1: pull SS_N low, send the 16-bit angle, then 0x0000. The second word read back on MISO is the sine.
4. Release SS_N, then do a second frame with one 0x0000 word. The word read back on MISO is the cosine.
5. Convert both results from signed Q1.15 to a decimal value (divide by 32768) and compare with sin/cos of the angle.

The cocotb testbench in `test/` does this at 10 MHz clock and about 200 kHz SPI clock. It checks cardinal angles, boundary angles, 100 random angles (tolerance 0.002) and recovery from a reset in the middle of a calculation.

| Pin    | Function     |
|--------|--------------|
| ui[0]  | SPI SS_N     |
| ui[1]  | SPI SCK      |
| ui[2]  | SPI MOSI     |
| uo[0]  | SPI MISO     |
| uo[1]  | CORDIC done  |

## External hardware

A SPI controller is needed, such as a microcontroller (an RP2040 was used for development) or a USB-SPI adapter. No other external hardware is required.
