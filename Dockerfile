FROM python:3.10\nWORKDIR /app\nCOPY . /app\nRUN pip install -r requirements.txt\nCMD ['uvicorn', 'main.main:app', '--host', '0.0.0.0', '--port', '80']
