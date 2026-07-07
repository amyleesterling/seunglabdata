/**
 * Subscribe form -> Google Sheet bridge for connectome.quest
 *
 * SETUP (one time, ~2 minutes):
 *  1. Open the Subscribers spreadsheet:
 *     https://docs.google.com/spreadsheets/d/1AkbBdIjeLya7wb1xzbGnBK14vVeSh6xY-c7sauMsqNU/edit
 *  2. Extensions > Apps Script. Delete any starter code, paste this whole file, Save.
 *  3. Deploy > New deployment > (gear) Web app.
 *       - Description: subscribe endpoint
 *       - Execute as: Me
 *       - Who has access: Anyone
 *     Click Deploy, authorize when prompted.
 *  4. Copy the "Web app" URL (ends in /exec).
 *  5. Paste that URL into ENDPOINT in index.html and redeploy the site.
 *
 * To change the code later you must Deploy > Manage deployments > edit (pencil)
 * > Version: New version, so the live /exec URL stays the same.
 */

var SHEET_ID = '1AkbBdIjeLya7wb1xzbGnBK14vVeSh6xY-c7sauMsqNU';
var SHEET_NAME = 'Subscribers'; // rename a tab to this, or the first tab is used

function doPost(e) {
  var lock = LockService.getScriptLock();
  lock.tryLock(30000);
  try {
    var ss = SpreadsheetApp.openById(SHEET_ID);
    var sheet = ss.getSheetByName(SHEET_NAME) || ss.getSheets()[0];

    // Write a header row the first time.
    if (sheet.getLastRow() === 0) {
      sheet.appendRow(['Timestamp', 'Name', 'Email', 'Country', 'EyeWire username']);
    }

    var p = (e && e.parameter) ? e.parameter : {};
    var email = String(p.email || '').trim().toLowerCase();

    // duplicate guard: skip if this email is already subscribed (column C = Email)
    if (email && sheet.getLastRow() > 1) {
      var existing = sheet.getRange(2, 3, sheet.getLastRow() - 1, 1).getValues();
      for (var i = 0; i < existing.length; i++) {
        if (String(existing[i][0]).trim().toLowerCase() === email) {
          return ContentService
            .createTextOutput(JSON.stringify({ result: 'duplicate' }))
            .setMimeType(ContentService.MimeType.JSON);
        }
      }
    }

    sheet.appendRow([
      new Date(),
      p.name || '',
      p.email || '',
      p.country || '',
      p.eyewire_username || ''
    ]);

    return ContentService
      .createTextOutput(JSON.stringify({ result: 'success' }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ result: 'error', message: String(err) }))
      .setMimeType(ContentService.MimeType.JSON);
  } finally {
    lock.releaseLock();
  }
}

// Lets you open the /exec URL in a browser to confirm it deployed.
function doGet() {
  return ContentService
    .createTextOutput('Subscribe endpoint is live.')
    .setMimeType(ContentService.MimeType.TEXT);
}
