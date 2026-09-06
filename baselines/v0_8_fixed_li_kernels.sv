
module kernel_a_li (
    input  logic        clk,
    input  logic        reset,
    input  logic        go,
    input  logic [31:0] x,
    output logic [31:0] out,
    output logic        done
);

    localparam integer LATENCY = 2;
    localparam integer COUNT_W =
        (LATENCY <= 1) ? 1 : $clog2(LATENCY + 1);

    logic busy;
    logic [COUNT_W-1:0] count;
    logic [31:0] saved_x;

    always_ff @(posedge clk) begin
        if (reset) begin
            busy    <= 1'b0;
            count   <= '0;
            saved_x <= '0;
            out     <= '0;
            done    <= 1'b0;
        end else begin
            done <= 1'b0;

            if (!busy && go) begin
                saved_x <= x;

                if (LATENCY == 1) begin
                    out  <= x + 32'd1;
                    done <= 1'b1;
                    busy <= 1'b0;
                end else begin
                    busy  <= 1'b1;
                    count <= COUNT_W'(LATENCY - 1);
                end
            end else if (busy) begin
                if (count == 1) begin
                    out   <= saved_x + 32'd1;
                    done  <= 1'b1;
                    busy  <= 1'b0;
                    count <= '0;
                end else begin
                    count <= count - 1'b1;
                end
            end
        end
    end

endmodule


module kernel_b_li (
    input  logic        clk,
    input  logic        reset,
    input  logic        go,
    input  logic [31:0] x,
    output logic [31:0] out,
    output logic        done
);

    localparam integer LATENCY = 5;
    localparam integer COUNT_W =
        (LATENCY <= 1) ? 1 : $clog2(LATENCY + 1);

    logic busy;
    logic [COUNT_W-1:0] count;
    logic [31:0] saved_x;

    always_ff @(posedge clk) begin
        if (reset) begin
            busy    <= 1'b0;
            count   <= '0;
            saved_x <= '0;
            out     <= '0;
            done    <= 1'b0;
        end else begin
            done <= 1'b0;

            if (!busy && go) begin
                saved_x <= x;

                if (LATENCY == 1) begin
                    out  <= x + 32'd2;
                    done <= 1'b1;
                    busy <= 1'b0;
                end else begin
                    busy  <= 1'b1;
                    count <= COUNT_W'(LATENCY - 1);
                end
            end else if (busy) begin
                if (count == 1) begin
                    out   <= saved_x + 32'd2;
                    done  <= 1'b1;
                    busy  <= 1'b0;
                    count <= '0;
                end else begin
                    count <= count - 1'b1;
                end
            end
        end
    end

endmodule
