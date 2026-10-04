/*
 * Copyright (c) 2026 Yash
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module tt_um_yash_cordic_spi (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // always 1 when powered
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

  wire w_miso;
  wire w_done;

  cordic_top u_cordic_top (
      .i_clk         (clk),
      .i_rst_n       (rst_n),
      .i_ss_n        (ui_in[0]),
      .i_sck         (ui_in[1]),
      .i_mosi        (ui_in[2]),
      .o_miso        (w_miso),
      .o_cordic_done (w_done)
  );

  assign uo_out  = {6'b0, w_done, w_miso};  // [0]=miso, [1]=done
  assign uio_out = 8'b0;
  assign uio_oe  = 8'b0;

  wire _unused = &{ena, ui_in[7:3], uio_in, 1'b0};

endmodule

`default_nettype wire
