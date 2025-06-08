import shutil
import os
import sys

# Ensure the project root is in sys.path for robust imports
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import create_app

# --- Start of CSV reset logic ---
source_file_path = os.path.join("data", "reservations.csv.org.csv")
destination_file_path = os.path.join("data", "reservations.csv")

if os.path.exists(source_file_path):
    try:
        # Ensure the 'data' directory exists; os.path.join doesn't create it.
        # shutil.copy2 will create the destination_file if it doesn't exist,
        # but it's good practice if the directory is confirmed.
        # However, for this specific task, we assume 'data/' exists.
        shutil.copy2(source_file_path, destination_file_path)
        print(f"[INFO] Successfully copied '{source_file_path}' to '{destination_file_path}'")
    except Exception as e:
        print(f"[ERROR] Failed to copy '{source_file_path}' to '{destination_file_path}': {e}")
        # Decide if this error is critical. For now, just print and continue.
else:
    print(f"[WARNING] Source file '{source_file_path}' not found. Skipping reset of 'reservations.csv'.")
# --- End of CSV reset logic ---

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5001)
