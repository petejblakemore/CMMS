
#this is a startup script for my cmms system...
export CMMS_SECRET_KEY="the-rain-in-spain-falls-mainly"
cd /Users/pete/CMMS
uvicorn cmms_ui:app --host 0.0.0.0 --port 8000 --reload \
  --ssl-keyfile=192.168.1.224+3-key.pem \
  --ssl-certfile=192.168.1.224+3.pem