# Work Plan: Fix Data Export Pipeline

**Objective**: Modify the `backend/run_full_pipeline.py` script to ensure it generates fresh analysis data before exporting the results to Google Sheets.

**Agent**: Sisyphus (Execution Agent)

**Context**: The current implementation of `run_full_pipeline.py` only calls the export function (`run_sheets_export_pipeline`), which results in stale data being sent to Google Sheets. The script must be updated to first execute the analysis and prediction functions (`run_orchestrated_analysis`, `run_prop_analysis_pipeline`) and then pass the fresh data to the export function.

---

### Step 1: Read the Target Script

To ensure you are working with the correct version of the file, read the contents of `backend/run_full_pipeline.py`.

```tool
read(filePath="backend/run_full_pipeline.py")
```

### Step 2: Modify the Script Logic

Update the script to perform the analysis before the export. Use the `edit` tool with the following changes. This edit will:
1.  Import all the necessary pipeline functions.
2.  Rewrite the `main` function to orchestrate the full data flow: analysis -> props -> export.

```tool
edit(
  filePath="backend/run_full_pipeline.py",
  edits=[
    {
      "op": "replace",
      "pos": "8#HQ",
      "end": "9#PS",
      "lines": "from app.services.analysis_runner import run_orchestrated_analysis, run_sheets_export_pipeline, run_prop_analysis_pipeline"
    },
    {
      "op": "replace",
      "pos": "13#XJ",
      "end": "17#JK",
      "lines": [
        "    logger.info(\"Step 1: Running orchestrated analysis to generate new predictions...\")",
        "    analysis_data = run_orchestrated_analysis()",
        "    ncaab_data = analysis_data.get(\"ncaab\")",
        "    nba_data = analysis_data.get(\"nba\")",
        "    ",
        "    logger.info(\"Step 2: Running prop analysis pipeline...\")",
        "    prop_data = run_prop_analysis_pipeline()",
        "",
        "    logger.info(\"Step 3: Exporting all fresh data to Google Sheets...\")",
        "    export_result = run_sheets_export_pipeline(",
        "        ncaab_data=ncaab_data,",
        "        nba_data=nba_data,",
        "        prop_data=prop_data",
        "    )",
        "",
        "    if export_result:",
        "        logger.info(\"Pipeline completed successfully and data exported to Google Sheets.\")",
        "        return True",
        "    else:",
        "        logger.error(\"Google Sheets export failed. Check logs for details.\")",
        "        return False"
      ]
    }
  ]
)
```

### Step 3: Validate the Fix

Execute the modified script. Check the output logs to confirm that the analysis steps run before the export step and that there are no errors.

```tool
bash(command="python3 backend/run_full_pipeline.py", description="Execute the fixed pipeline script.")
```

**Success Criteria**:
- The script runs to completion without errors.
- The logs show "Step 1", "Step 2", and "Step 3" messages in the correct order.
- The log message "Pipeline completed successfully..." is printed.

### Step 4: Final Cleanup

Once the pipeline has been validated, remove the temporary script you created in the last session.

```tool
bash(command="rm temp_run_pipeline.py", description="Remove the old temporary pipeline script.")
```

---
**Plan Complete.** Awaiting execution.
