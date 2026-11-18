/* Label rendering and QR drawing. Layout spec: docs/04-qr-label-spec.md.
   This file only draws the text it is given. QR text is assembled on the server
   (app/services/qr_payload.py) and must never be rebuilt here. */
(function () {
  qrcode.stringToBytes = qrcode.stringToBytesFuncs['UTF-8'];

  const QUIET_LABEL = 2;      // quiet-zone modules on printed labels
  const QUIET_PNG = 4;        // quiet-zone modules in downloaded PNGs
  const MIN_MODULE_MM = 0.4;  // density warning threshold (provisional, see docs/08 A-11)
  const QR_PAD_MM = 0.8;

  function makeQr(text) { const q = qrcode(0, 'M'); q.addData(text, 'Byte'); q.make(); return q; }

  function qrSvg(qr, margin) {
    const n = qr.getModuleCount(), size = n + margin * 2;
    let d = '';
    for (let r = 0; r < n; r++) for (let c = 0; c < n; c++)
      if (qr.isDark(r, c)) d += `M${c + margin},${r + margin}h1v1h-1z`;
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}" shape-rendering="crispEdges">` +
           `<rect width="${size}" height="${size}" fill="#fff"/><path d="${d}" fill="#000"/></svg>`;
  }

  function qrPngBytes(qr, px = 10) {
    const n = qr.getModuleCount(), size = (n + QUIET_PNG * 2) * px;
    const cv = document.createElement('canvas'); cv.width = cv.height = size;
    const ctx = cv.getContext('2d');
    ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, size, size); ctx.fillStyle = '#000';
    for (let r = 0; r < n; r++) for (let c = 0; c < n; c++)
      if (qr.isDark(r, c)) ctx.fillRect((c + QUIET_PNG) * px, (r + QUIET_PNG) * px, px, px);
    return new Promise(res => cv.toBlob(b => b.arrayBuffer().then(ab => res(new Uint8Array(ab))), 'image/png'));
  }

  function geometry(size) {
    const [lw, lh] = size.split('x').map(Number);
    const qw = Math.min(lh, lw * 0.45);
    const fs = Math.min((lh / 3) * 0.3, (lw - qw) / 14);
    return { lw, lh, qw, fs, kw: fs * 4.4 };
  }

  /* Printed width of one QR module in mm for this text on this label size.
     Throws if the text exceeds QR capacity. */
  function density(text, size) {
    const qr = makeQr(text), n = qr.getModuleCount(), g = geometry(size);
    const moduleMm = (g.qw - QR_PAD_MM * 2) / (n + QUIET_LABEL * 2);
    return { version: (n - 17) / 4, modules: n, moduleMm, tooDense: moduleMm < MIN_MODULE_MM };
  }

  const el = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  };

  /* One label: QR on the left, a three-row table on the right.
     The table has exactly these rows and must not gain others (docs/08 D-03). */
  function tagNode(row) {
    const t = el('div', 'tag');
    const q = el('div', 'qr'); q.innerHTML = qrSvg(makeQr(row.payload), QUIET_LABEL); t.appendChild(q);
    const tb = el('table'), body = el('tbody');
    const add = (k, v, cls) => {
      const tr = el('tr', cls);
      tr.appendChild(el('td', 'k', k));
      const td = el('td', 'v', v); td.title = v; tr.appendChild(td);
      body.appendChild(tr);
    };
    add('序號', row.serial, 'sn');
    add('型號', row.model);
    add('叫修電話', row.tel, 'tel');
    tb.appendChild(body); t.appendChild(tb);
    return t;
  }

  function renderSheet(sheet, rows, size, layout) {
    const g = geometry(size);
    sheet.style.setProperty('--lw', g.lw + 'mm');
    sheet.style.setProperty('--lh', g.lh + 'mm');
    sheet.style.setProperty('--qw', g.qw.toFixed(2) + 'mm');
    sheet.style.setProperty('--fs', g.fs.toFixed(2) + 'mm');
    sheet.style.setProperty('--kw', g.kw.toFixed(2) + 'mm');
    sheet.className = 'sheet' + (layout === 'single' ? ' single' : '');
    sheet.innerHTML = '';
    const wrap = el('div', 'tags');
    rows.forEach(r => wrap.appendChild(tagNode(r)));
    sheet.appendChild(wrap);
    let st = document.getElementById('pageStyle');
    if (!st) { st = document.createElement('style'); st.id = 'pageStyle'; document.head.appendChild(st); }
    st.textContent = layout === 'single'
      ? `@media print { @page { size: ${g.lw}mm ${g.lh}mm; margin: 0; } }`
      : `@media print { @page { size: A4; margin: 8mm; } }`;
  }

  const safeName = s => String(s).replace(/[\\/:*?"<>|\s]+/g, '_');
  function download(blob, name) {
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }

  function csvBlob(rows) {
    const q = v => `"${String(v).replace(/"/g, '""')}"`;
    const head = ['序號', '型號', '出貨日期', '客戶訂單編號', '內部訂單編號', '叫修電話', 'QR內容'];
    const lines = rows.map(r => [r.serial, r.model, r.ship_date, r.cust_po, r.int_po, r.tel, r.payload].map(q).join(','));
    return new Blob(['﻿' + [head.map(q).join(','), ...lines].join('\r\n')], { type: 'text/csv' });
  }

  // Minimal ZIP writer (stored, no compression).
  const crcTable = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
  const crc32 = b => { let c = 0xFFFFFFFF; for (let i = 0; i < b.length; i++) c = crcTable[(c ^ b[i]) & 0xFF] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; };
  function makeZip(files) {
    const enc = new TextEncoder(), parts = [], central = []; let offset = 0;
    for (const f of files) {
      const name = enc.encode(f.name), crc = crc32(f.data), sz = f.data.length;
      const lh = new DataView(new ArrayBuffer(30));
      lh.setUint32(0, 0x04034b50, true); lh.setUint16(4, 20, true); lh.setUint16(6, 0x0800, true);
      lh.setUint32(14, crc, true); lh.setUint32(18, sz, true); lh.setUint32(22, sz, true); lh.setUint16(26, name.length, true);
      parts.push(new Uint8Array(lh.buffer), name, f.data);
      const ch = new DataView(new ArrayBuffer(46));
      ch.setUint32(0, 0x02014b50, true); ch.setUint16(4, 20, true); ch.setUint16(6, 20, true); ch.setUint16(8, 0x0800, true);
      ch.setUint32(16, crc, true); ch.setUint32(20, sz, true); ch.setUint32(24, sz, true); ch.setUint16(28, name.length, true);
      ch.setUint32(42, offset, true);
      central.push(new Uint8Array(ch.buffer), name);
      offset += 30 + name.length + sz;
    }
    const cdSize = central.reduce((a, b) => a + b.length, 0);
    const end = new DataView(new ArrayBuffer(22));
    end.setUint32(0, 0x06054b50, true); end.setUint16(8, files.length, true); end.setUint16(10, files.length, true);
    end.setUint32(12, cdSize, true); end.setUint32(16, offset, true);
    return new Blob([...parts, ...central, new Uint8Array(end.buffer)], { type: 'application/zip' });
  }
  async function zipBlob(rows) {
    const files = [];
    for (const r of rows) files.push({ name: `${safeName(r.serial)}.png`, data: await qrPngBytes(makeQr(r.payload)) });
    return makeZip(files);
  }

  window.ShipLabel = { makeQr, qrSvg, density, renderSheet, tagNode, csvBlob, zipBlob, download, safeName,
                       MIN_MODULE_MM, QUIET_LABEL };
})();
