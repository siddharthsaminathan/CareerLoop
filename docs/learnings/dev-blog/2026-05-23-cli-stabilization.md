# Dev Blog — 2026-05-23: CLI Stabilization & Ledger Safety

## What Was Done
- Fixed Pydantic validation errors that were crashing the CLI startup by reverting the `sync_profile_data` LangChain tool back to a standard Python function.
- Implemented persistent user authentication for the Terminal CLI by caching the user's email in `~/.careerloop_session`.
- Repaired a corrupted `careerloop/ledger.json` file which resulted from a mid-save process termination.
- Re-architected `careerloop/application_ledger.py`'s `_save` method to use atomic file replacements (`os.replace`) with a `.tmp` file, entirely preventing future JSON corruption.

## Key Decisions
- **Removing Pydantic Tools on Startup:** To prevent LangGraph from raising `ValidationError` on startup due to strict typing in `sync_profile_data`, I decided to just use a standard Python function and invoke it directly from the graph logic.
- **Atomic File Saves:** Instead of adding complex file locking, I chose `os.replace(tmp_path, final_path)` because it guarantees atomic writes at the OS level across POSIX and Windows, ensuring the ledger can never be corrupted by a sudden `SIGKILL`.

## Issues Encountered
- **Auth Amnesia:** The mock `authenticate_cli_user` flow wasn't caching anything, so the user was forced to type their email on every boot, causing immense frustration.
- **Terminal Paste Buffer:** Because the CLI was crashing, it dropped the user into their `zsh` shell while they were pasting their resume, resulting in their `zsh` trying to execute markdown headers.
- **JSON Corruption:** A process kill during a 600KB file save corrupted `ledger.json` and broke the `DailyRunner` (`Expecting property name enclosed in double quotes: line 20775 column 5`).

## Files Changed
- `careerloop/chat_cli.py`
- `careerloop/application_ledger.py`
- `careerloop/tools/sync_profile.py`
- `careerloop/session/supervisor_graph.py`
- `careerloop/ledger.json`

## Next Session
- Re-examine the integration of the India Fit Engine inside the `DailyRunner` to ensure the deduplication logic functions accurately when pulling from multiple portal endpoints.
