@echo off
rem llhsync: pull -> ingest -> commit -> push  (for scheduled task)
python "%~dp0llh.py" sync %*
