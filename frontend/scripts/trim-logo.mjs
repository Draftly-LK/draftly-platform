/**
 * One-off: trim the transparent margin off the supplied logo PNGs.
 *
 * The source files are 701x700 with the typewriter mark sitting in roughly the
 * middle third, so rendering them at 32 px leaves a ~14 px mark. Trimming to
 * the alpha bounding box lets every placement size the mark directly.
 *
 * Pure Node (zlib only) — the frontend does not carry an image toolchain.
 * Run: node scripts/trim-logo.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import zlib from "node:zlib";

const CRC_TABLE = (() => {
  const table = new Int32Array(256);
  for (let n = 0; n < 256; n += 1) {
    let c = n;
    for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    table[n] = c;
  }
  return table;
})();

function crc32(buf) {
  let c = -1;
  for (let i = 0; i < buf.length; i += 1) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ -1) >>> 0;
}

function chunk(type, data) {
  const out = Buffer.alloc(data.length + 12);
  out.writeUInt32BE(data.length, 0);
  out.write(type, 4, "ascii");
  data.copy(out, 8);
  out.writeUInt32BE(crc32(out.subarray(4, 8 + data.length)), 8 + data.length);
  return out;
}

/** Decode an 8-bit RGBA (colour type 6) PNG into a flat pixel buffer. */
function decode(file) {
  const buf = fs.readFileSync(file);
  const width = buf.readUInt32BE(16);
  const height = buf.readUInt32BE(20);
  if (buf[24] !== 8 || buf[25] !== 6) {
    throw new Error(`${file}: expected 8-bit RGBA, got depth ${buf[24]} type ${buf[25]}`);
  }

  const idat = [];
  let offset = 8;
  while (offset < buf.length) {
    const length = buf.readUInt32BE(offset);
    const type = buf.toString("ascii", offset + 4, offset + 8);
    if (type === "IDAT") idat.push(buf.subarray(offset + 8, offset + 8 + length));
    offset += length + 12;
  }

  const raw = zlib.inflateSync(Buffer.concat(idat));
  const stride = width * 4;
  const pixels = Buffer.alloc(height * stride);

  for (let y = 0; y < height; y += 1) {
    const filter = raw[y * (stride + 1)];
    const line = raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1));
    for (let x = 0; x < stride; x += 1) {
      const a = x >= 4 ? pixels[y * stride + x - 4] : 0;
      const b = y > 0 ? pixels[(y - 1) * stride + x] : 0;
      const c = x >= 4 && y > 0 ? pixels[(y - 1) * stride + x - 4] : 0;
      let value = line[x];
      if (filter === 1) value += a;
      else if (filter === 2) value += b;
      else if (filter === 3) value += (a + b) >> 1;
      else if (filter === 4) {
        const p = a + b - c;
        const pa = Math.abs(p - a);
        const pb = Math.abs(p - b);
        const pc = Math.abs(p - c);
        value += pa <= pb && pa <= pc ? a : pb <= pc ? b : c;
      }
      pixels[y * stride + x] = value & 0xff;
    }
  }
  return { width, height, pixels };
}

/** Encode a flat RGBA buffer back to a PNG with no row filtering. */
function encode(file, width, height, pixels) {
  const stride = width * 4;
  const raw = Buffer.alloc(height * (stride + 1));
  for (let y = 0; y < height; y += 1) {
    raw[y * (stride + 1)] = 0;
    pixels.copy(raw, y * (stride + 1) + 1, y * stride, (y + 1) * stride);
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8;
  ihdr[9] = 6;
  fs.writeFileSync(
    file,
    Buffer.concat([
      Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
      chunk("IHDR", ihdr),
      chunk("IDAT", zlib.deflateSync(raw, { level: 9 })),
      chunk("IEND", Buffer.alloc(0)),
    ]),
  );
}

/**
 * Crop to the alpha bounding box, then re-pad to a square so every placement
 * can use one aspect ratio and the mark stays optically centred.
 */
function trim(source, target) {
  const { width, height, pixels } = decode(source);
  let top = height;
  let left = width;
  let right = -1;
  let bottom = -1;

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      // 8 rather than 0: the source has a faint anti-aliased halo.
      if (pixels[(y * width + x) * 4 + 3] > 8) {
        if (y < top) top = y;
        if (y > bottom) bottom = y;
        if (x < left) left = x;
        if (x > right) right = x;
      }
    }
  }
  if (right < 0) throw new Error(`${source}: fully transparent`);

  const cropW = right - left + 1;
  const cropH = bottom - top + 1;
  const side = Math.max(cropW, cropH);
  const padX = Math.floor((side - cropW) / 2);
  const padY = Math.floor((side - cropH) / 2);
  const out = Buffer.alloc(side * side * 4);

  for (let y = 0; y < cropH; y += 1) {
    const from = ((top + y) * width + left) * 4;
    pixels.copy(out, ((padY + y) * side + padX) * 4, from, from + cropW * 4);
  }

  encode(target, side, side, out);
  console.log(
    `${path.basename(source)} ${width}x${height} → ${path.basename(target)} ${side}x${side} ` +
      `(content ${cropW}x${cropH} at ${left},${top})`,
  );
}

const here = path.dirname(fileURLToPath(import.meta.url));
const dir = path.join(here, "..", "public", "images");
for (const name of ["blue", "white", "black"]) {
  trim(path.join(dir, `logo-tw-${name}.png`), path.join(dir, `logo-mark-${name}.png`));
}
