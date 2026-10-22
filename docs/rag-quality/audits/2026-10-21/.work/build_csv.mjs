import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Workbook } from '@oai/artifact-tool';

const directory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const rows = JSON.parse(await fs.readFile(path.join(directory, 'csv-payload.json'), 'utf8'));
const headers = Object.keys(rows[0]);
const matrix = [headers, ...rows.map(row => headers.map(key => row[key]))];
const workbook = Workbook.create();
const sheet = workbook.worksheets.add('Auditoria');
sheet.getRangeByIndexes(0, 0, matrix.length, headers.length).values = matrix;
sheet.showGridLines = false;
sheet.getRange('A1:F5').format.font = {name: 'Arial', size: 10};
sheet.getRange('A1:F5').format.columnWidth = 24;
sheet.getRange('A1:F5').format.rowHeight = 50;
sheet.getRange('A1:F5').format.wrapText = true;
sheet.getRange('A1:F1').format.fill = '#243B53';
sheet.getRange('A1:F1').format.font = {name: 'Arial', size: 10, bold: true, color: '#FFFFFF'};
sheet.getRange('A1:A5').format.columnWidth = 14;
sheet.getRange('E1:F5').format.columnWidth = 36;
workbook.recalculate();
const authored = sheet.getRangeByIndexes(0, 0, matrix.length, headers.length).values;
for (let r = 0; r < matrix.length; r++) {
  for (let c = 0; c < headers.length; c++) {
    if ((authored[r][c] ?? '') !== (matrix[r][c] ?? '')) throw Error(`Cell changed at ${r},${c}`);
  }
}
const inspection = await workbook.inspect({kind: 'table', range: 'Auditoria!A1:F5', include: 'values', tableMaxRows: 5, tableMaxCols: 6, maxChars: 1800});
await fs.writeFile(path.join(directory, '.work', 'inspection.json'), inspection.ndjson);
if (!(await fs.stat(path.join(directory, '.work', 'preview.png')).catch(() => null))) {
  const preview = await workbook.render({sheetName: 'Auditoria', range: 'A1:F5', scale: 1.5, format: 'png'});
  await fs.writeFile(path.join(directory, '.work', 'preview.png'), new Uint8Array(await preview.arrayBuffer()));
}
// CSV is the explicitly requested deliverable. Serialize the authored worksheet,
// retaining multiline response/evidence cells, accents, quotes and identifiers.
const escape = value => `"${String(value ?? '').replaceAll('"', '""')}"`;
await fs.writeFile(path.join(directory, 'AUDITORIA_76_CASOS.csv'), '\uFEFF' + authored.map(row => row.map(escape).join(',')).join('\r\n') + '\r\n', 'utf8');
await fs.writeFile(path.join(directory, '.work', 'csv-check.json'), JSON.stringify({rows: rows.length, columns: headers.length, uniqueIds: new Set(rows.map(row => row.ID)).size, allAuthoredCellsMatchPayload: true, formulasIntroduced: 0}, null, 2));
console.log(JSON.stringify({exportedRows: rows.length, columns: headers.length, sourceValuesPreserved: true}));
