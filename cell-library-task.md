## Cell Library: dataset scoping + spreadsheet write-back

Branch: `eyewire-ii-community`

### Background / current behavior
`src/components/CellLibraryPanel.vue` builds its list from two sources:
- Google Sheet — `queue.loadFromSheet(sheetSource)` where
  `sheetSource = queue.sheetUrl || EYEWIRE_II_CAVE_CONFIG.cellLibrarySheetUrl`
  (source sheet: https://docs.google.com/spreadsheets/d/1SdepJzadXMz5TC-5DFZxUyDJk7efEPP39HE0hmUAJjU/edit)
- Supabase tasks — `backend.loadTasks('eyewire_ii')` (claim/completion status truth)

Each cell currently has: `segId, index, nucCoords, somaCoords, notes, taskId, status, assignedTo, finalSegId, claimPoint`.
**There is no `dataset` field on the base cell, and no dataset filtering on the main list.** The library therefore mixes cells from all datasets (pinky_sandbox, stroeh_mouse_retina, minnie65, etc.).

### Requirement 1 — Scope the Cell Library to the current dataset
- Only show cells belonging to the currently selected dataset.
- The Cell Library input (adding/looking up a cell) should **require a dataset to be selected** first.
- Wire to the existing dataset config/selection:
  - `src/components/DatasetSelectorPanel.vue`
  - `config/datastack-dataset.json` (dataset → CAVE datastack map)
  - `src/datasets.ts`
  - active dataset lives in the store (`segAnnotation` / `nge_dataset_preference`)
- **Blocker to resolve:** cells from the sheet carry no dataset today. Decide the source of truth:
  - add a `dataset` column to the source sheet and parse it in `loadFromSheet`, and/or
  - derive dataset from the segment ID space / datastack.
  Filtering can't be correct until each cell has a dataset.

### Requirement 2 — Write back to the source spreadsheet
- Write-back plumbing already exists and can be extended:
  - `src/widgets/google_sheets_auth.ts` — `getAccessToken()`, service account
    `eyewire-ii-spreadsheet@eyewire-ii.iam.gserviceaccount.com`,
    scope `https://www.googleapis.com/auth/spreadsheets` (read+write).
  - queue store / `src/components/ProofreadingQueuePanel.vue` — existing
    `writeClaimToSheet()` and `writeToSheetColumn()` helpers.
- Extend these to write back the intended Cell Library fields (define which: e.g. dataset, cell type, status/completion, notes, assignee) to the correct rows/columns.
- Confirm row-matching strategy (match by `segId`/`index`) and append-vs-update semantics.

### Open questions
- Which fields should write back to the sheet, and should it update in place or append?
- Add a `dataset` column to the sheet, or infer dataset from the segment ID space?
- Should the dataset selector in the Cell Library default to the app's active dataset, or be an independent picker?

### Acceptance criteria
- [ ] Cell Library shows only cells for the selected/active dataset.
- [ ] Adding/looking up a cell requires a dataset selection.
- [ ] Edits from the Cell Library persist back to the source Google Sheet (verified by reading the sheet after a write).
- [ ] Existing claim/complete write-back still works.

### Relevant files
- `src/components/CellLibraryPanel.vue`
- `src/components/ProofreadingQueuePanel.vue`
- `src/components/DatasetSelectorPanel.vue`
- `src/widgets/google_sheets_auth.ts`
- `config/datastack-dataset.json`, `src/datasets.ts`
