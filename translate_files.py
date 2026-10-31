import os
import sys
from langdetect import detect, LangDetectException
from googletrans import Translator
import time

def translate_and_rename(directory_path):
    # Initialize the Google Translator
    translator = Translator()
    
    # Check if directory exists
    if not os.path.exists(directory_path):
        print(f"Error: Directory '{directory_path}' does not exist.")
        return

    # Iterate over all items in the directory
    for filename in os.listdir(directory_path):
        # Skip hidden files like .DS_Store
        if filename.startswith('.'):
            continue
            
        # Separate the name from the extension
        name_without_ext, ext = os.path.splitext(filename)
        
        try:
            # Detect language of the filename
            lang = detect(name_without_ext)
            
            # If the detected language is Japanese ('ja')
            if lang == 'ja':
                print(f"Detected Japanese: '{filename}'")
                
                # Translate to English
                translation = translator.translate(name_without_ext, src='ja', dest='en')
                translated_name = translation.text
                
                # Sanitize the new filename (remove invalid character slashes)
                sanitized_name = translated_name.replace('/', '-').replace('\\', '-')
                new_filename = f"{sanitized_name}{ext}"
                
                # Build full paths
                old_file_path = os.path.join(directory_path, filename)
                new_file_path = os.path.join(directory_path, new_filename)
                
                # Rename the file
                os.rename(old_file_path, new_file_path)
                print(f"Renamed to: '{new_filename}'\n")
                
                # Polite pause to avoid getting rate-limited by Google
                time.sleep(1)
                
            else:
                print(f"Skipping (Not Japanese): '{filename}'")
                
        except LangDetectException:
            # Thrown if the filename is purely numbers/symbols and can't be analyzed
            print(f"Skipping (Undetectable text): '{filename}'")
        except Exception as e:
            print(f"Error processing '{filename}': {e}")

if __name__ == "__main__":
    # Expects the directory path as a command-line argument
    if len(sys.argv) < 2:
        print("Usage: python translate_files.py /path/to/your/directory")
    else:
        target_dir = sys.argv[1]
        translate_and_rename(target_dir)

