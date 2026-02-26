python -m PyInstaller --onefile --name talker_bridge --icon=talker_mic.ico --exclude-module torch --exclude-module faster_whisper --exclude-module openai main.py
