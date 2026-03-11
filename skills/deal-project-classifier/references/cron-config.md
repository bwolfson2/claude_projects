# Classifier Cron Configuration

## Task: classify-batch-2h

**Schedule:** Every 2 hours, Mon–Fri
**Cron expression:** `0 8,10,12,14,16,18,20 * * 1-5`
**Task name:** `classify-batch-2h`

### Prompt for Scheduled Task

```
Classify any unclassified emails and transcripts in the VFT ingestion database and update the deal/project pipeline.

Steps:
1. Run the batch classifier:
   python skills/deal-project-classifier/scripts/classify_batch.py --rebuild-index
2. Review the output — check for any low-confidence matches or auto-created entries.
3. Apply the classification results to deals.json and projects.json:
   python skills/deal-project-classifier/scripts/apply_updates.py
4. The apply step also triggers tracker-sync to update VFT-Master-Tracker.xlsx.

Success criteria: All unclassified items in fund/metadata/db/ingestion.db are classified. deals.json and projects.json updated with new last_touch dates and any auto-created entries. VFT-Master-Tracker.xlsx reflects the changes.
Working directory: The due_diligences folder synced via Google Drive for Desktop.
```
