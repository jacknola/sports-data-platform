/**
 * Sports Betting Model — Raw Data Cleaner
 * Reads from "Raw_Data", outputs cleaned/split data to "Clean_Model".
 */

const VALID_TEAMS = new Set([
  "ATL","BOS","BKN","CHA","CHI","CLE","DAL","DEN","DET","GSW",
  "HOU","IND","LAC","LAL","MEM","MIA","MIL","MIN","NOP","NYK",
  "OKC","ORL","PHI","PHX","POR","SAC","SAS","TOR","UTA","WAS"
]);

const STAT_COLS = ["Points", "Rebounds", "Assists", "3PTM", "Steals", "Blocks"];

const OUTPUT_HEADERS = [
  "Date", "Team", "Player", "Position",
  "Points Line", "Points Proj",
  "Rebounds Line", "Rebounds Proj",
  "Assists Line", "Assists Proj",
  "3PTM Line", "3PTM Proj",
  "Steals Line", "Steals Proj",
  "Blocks Line", "Blocks Proj"
];

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("Betting Model")
    .addItem("Clean Raw Data", "cleanRawData")
    .addToUi();
}

function cleanRawData() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  const rawSheet = ss.getSheetByName("Raw_Data");
  if (!rawSheet) {
    SpreadsheetApp.getUi().alert('Sheet "Raw_Data" not found.');
    return;
  }

  const rawData = rawSheet.getDataRange().getValues();
  if (rawData.length === 0) {
    SpreadsheetApp.getUi().alert("Raw_Data is empty.");
    return;
  }

  // Create or clear destination sheet
  let cleanSheet = ss.getSheetByName("Clean_Model");
  if (cleanSheet) {
    cleanSheet.clear();
  } else {
    cleanSheet = ss.insertSheet("Clean_Model");
  }

  const output = [OUTPUT_HEADERS];
  let currentDate = "";

  // Try to find column indices from a header row (first row)
  const headerRow = rawData[0].map(function(c) {
    return String(c).trim().toLowerCase();
  });

  // Heuristic: detect header row
  let startRow = 0;
  const teamColIdx = findColIndex(headerRow, ["team", "tm"]);
  const playerColIdx = findColIndex(headerRow, ["player", "name"]);
  const posColIdx = findColIndex(headerRow, ["position", "pos"]);

  // Build stat column index map from header
  const statColIndices = {};
  for (let i = 0; i < STAT_COLS.length; i++) {
    const idx = findColIndex(headerRow, [STAT_COLS[i].toLowerCase(), STAT_COLS[i].toLowerCase().slice(0, 3)]);
    if (idx >= 0) statColIndices[STAT_COLS[i]] = idx;
  }

  const hasHeader = teamColIdx >= 0 && playerColIdx >= 0;
  if (hasHeader) startRow = 1;

  // Date pattern: YYYY-MM-DD anywhere in the row text
  const dateRegex = /(\d{4}-\d{2}-\d{2})/;

  for (let r = startRow; r < rawData.length; r++) {
    const row = rawData[r];
    const rowText = row.map(function(c) { return String(c); }).join(" ").trim();

    if (!rowText || rowText.length < 3) continue;

    // Check for date header row
    const dateMatch = rowText.match(dateRegex);
    if (dateMatch && isDateHeaderRow(rowText, dateMatch[1])) {
      currentDate = dateMatch[1];
      continue;
    }

    // Extract fields
    const team = extractTeam(row, teamColIdx);
    const player = extractField(row, playerColIdx, 1);
    const pos = extractField(row, posColIdx, -1);

    // Validate row: must have a valid team and non-garbage player name
    if (!team || !isValidPlayer(player)) continue;

    // Parse stats
    const outputRow = [currentDate, team, player, pos];

    for (let s = 0; s < STAT_COLS.length; s++) {
      const statName = STAT_COLS[s];
      const colIdx = statColIndices[statName];
      const raw = colIdx >= 0 ? String(row[colIdx]).trim() : "";
      const parsed = parseStat(raw);
      outputRow.push(parsed.line);
      outputRow.push(parsed.proj);
    }

    output.push(outputRow);
  }

  if (output.length <= 1) {
    SpreadsheetApp.getUi().alert("No valid rows found. Check Raw_Data formatting.");
    return;
  }

  // Write output
  cleanSheet.getRange(1, 1, output.length, OUTPUT_HEADERS.length).setValues(output);

  // Format header
  const headerRange = cleanSheet.getRange(1, 1, 1, OUTPUT_HEADERS.length);
  headerRange.setFontWeight("bold");
  headerRange.setBackground("#4a86c8");
  headerRange.setFontColor("#ffffff");
  cleanSheet.setFrozenRows(1);

  // Auto-resize columns
  for (let c = 1; c <= OUTPUT_HEADERS.length; c++) {
    cleanSheet.autoResizeColumn(c);
  }

  SpreadsheetApp.getUi().alert(
    "Done! Cleaned " + (output.length - 1) + " player rows into Clean_Model."
  );
}

// --- Helpers ---

function findColIndex(headerRow, candidates) {
  for (let i = 0; i < headerRow.length; i++) {
    for (let c = 0; c < candidates.length; c++) {
      if (headerRow[i] === candidates[c] || headerRow[i].indexOf(candidates[c]) >= 0) {
        return i;
      }
    }
  }
  return -1;
}

function isDateHeaderRow(rowText, dateStr) {
  // Date header rows are short or contain "@" (matchup format)
  var stripped = rowText.replace(dateStr, "").trim();
  return stripped.length < 30 || rowText.indexOf("@") >= 0 || rowText.indexOf("vs") >= 0;
}

function extractTeam(row, knownIdx) {
  // Try known column first
  if (knownIdx >= 0) {
    var val = String(row[knownIdx]).trim().toUpperCase();
    if (VALID_TEAMS.has(val)) return val;
  }
  // Scan row for a valid team abbreviation
  for (var i = 0; i < row.length; i++) {
    var cell = String(row[i]).trim().toUpperCase();
    if (VALID_TEAMS.has(cell)) return cell;
    // Check within longer strings (e.g. "ATL Hawks")
    var words = cell.split(/\s+/);
    for (var w = 0; w < words.length; w++) {
      if (VALID_TEAMS.has(words[w])) return words[w];
    }
  }
  return "";
}

function extractField(row, knownIdx, fallbackIdx) {
  if (knownIdx >= 0) return String(row[knownIdx]).trim();
  if (fallbackIdx >= 0 && fallbackIdx < row.length) return String(row[fallbackIdx]).trim();
  return "";
}

function isValidPlayer(name) {
  if (!name || name.length < 3) return false;
  // Must contain at least one letter
  if (!/[a-zA-Z]/.test(name)) return false;
  // Filter obvious garbage: names should have mostly letters/spaces/hyphens/periods
  var clean = name.replace(/[a-zA-Z\s\-\.']/g, "");
  return clean.length / name.length < 0.3;
}

function parseStat(raw) {
  var empty = { line: "", proj: "" };

  if (!raw || raw === "-/-" || raw === "N/A" || raw === "-" || raw === "n/a") {
    return empty;
  }

  // Handle slash-delimited "24.6/7.1"
  if (raw.indexOf("/") >= 0) {
    var parts = raw.split("/");
    return {
      line: parseNum(parts[0]),
      proj: parseNum(parts[1])
    };
  }

  // Single number — treat as line
  var num = parseFloat(raw);
  if (!isNaN(num)) {
    return { line: num, proj: "" };
  }

  return empty;
}

function parseNum(s) {
  if (!s) return "";
  var trimmed = String(s).trim();
  if (trimmed === "-" || trimmed === "N/A" || trimmed === "n/a" || trimmed === "") return "";
  var num = parseFloat(trimmed);
  return isNaN(num) ? "" : num;
}
