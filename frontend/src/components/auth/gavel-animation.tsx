"use client";

import { useEffect, useRef } from "react";

type GavelData = {
  width: number;
  height: number;
  fps: number;
  palette: [number, number, number][];
  frames: number[][];
};

const ASCII_RAMP =
  " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$";
const CELL_WIDTH = 7;
const CELL_HEIGHT = 12;

function isGavelData(value: unknown): value is GavelData {
  if (typeof value !== "object" || value === null) return false;
  const data = value as Partial<GavelData>;
  return (
    typeof data.width === "number" &&
    Number.isInteger(data.width) &&
    typeof data.height === "number" &&
    Number.isInteger(data.height) &&
    typeof data.fps === "number" &&
    data.fps > 0 &&
    Array.isArray(data.palette) &&
    data.palette.length > 0 &&
    Array.isArray(data.frames) &&
    data.frames.length > 0 &&
    data.frames[0]?.length === data.width * data.height
  );
}

/** Decorative replay of the authorized landing-page gavel asset. */
export function GavelAnimation() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const desktop = window.matchMedia("(min-width: 1024px)");
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let controller: AbortController | undefined;
    let animationFrame = 0;
    let startTime: number | undefined;
    let loaded: GavelData | undefined;

    function stop() {
      controller?.abort();
      controller = undefined;
      window.cancelAnimationFrame(animationFrame);
      animationFrame = 0;
      startTime = undefined;
    }

    function draw(data: GavelData, frameIndex: number) {
      const canvas = canvasRef.current;
      const context = canvas?.getContext("2d");
      const frame = data.frames[frameIndex];
      if (!canvas || !context || !frame) return;

      context.clearRect(0, 0, canvas.width, canvas.height);
      context.font =
        "11px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace";
      context.textBaseline = "top";

      for (let index = 0; index < frame.length; index += 1) {
        const paletteIndex = frame[index];
        if (!paletteIndex) continue;
        const color = data.palette[paletteIndex - 1];
        if (!color) continue;
        const brightness =
          (0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]) / 255;
        const glyph =
          ASCII_RAMP[Math.round(brightness * (ASCII_RAMP.length - 1))];
        if (!glyph || glyph === " ") continue;

        context.fillStyle = `rgb(${color[0]}, ${color[1]}, ${color[2]})`;
        context.fillText(
          glyph,
          (index % data.width) * CELL_WIDTH,
          Math.floor(index / data.width) * CELL_HEIGHT,
        );
      }
    }

    function play(data: GavelData) {
      if (reducedMotion.matches) {
        draw(data, Math.floor(data.frames.length / 2));
        return;
      }

      let previousFrame = -1;
      const tick = (now: number) => {
        startTime ??= now;
        const nextFrame =
          Math.floor(((now - startTime) * data.fps) / 1000) %
          data.frames.length;
        if (nextFrame !== previousFrame) {
          draw(data, nextFrame);
          previousFrame = nextFrame;
        }
        animationFrame = window.requestAnimationFrame(tick);
      };
      animationFrame = window.requestAnimationFrame(tick);
    }

    async function load() {
      stop();
      if (!desktop.matches) return;
      if (loaded) {
        play(loaded);
        return;
      }

      const request = new AbortController();
      controller = request;
      try {
        const response = await fetch("/animations/gavel-ascii.json", {
          signal: request.signal,
        });
        if (!response.ok) return;
        const data: unknown = await response.json();
        if (!isGavelData(data) || request.signal.aborted) return;
        loaded = data;
        const canvas = canvasRef.current;
        if (!canvas) return;
        canvas.width = data.width * CELL_WIDTH;
        canvas.height = data.height * CELL_HEIGHT;
        play(data);
      } catch {
        // The decoration must not interrupt registration when its asset fails.
      }
    }

    void load();
    desktop.addEventListener("change", load);
    reducedMotion.addEventListener("change", load);
    return () => {
      stop();
      desktop.removeEventListener("change", load);
      reducedMotion.removeEventListener("change", load);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      data-gavel-animation
      aria-hidden="true"
      className="block h-auto w-full max-w-[700px]"
    />
  );
}
