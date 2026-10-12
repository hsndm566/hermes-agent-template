import os
for key,value in {
'DATABASE_URL':'postgresql://localhost/booking','REDIS_URL':'redis://localhost:6379',
'EVOLUTION_INTERNAL_URL':'http://localhost:8080','EVOLUTION_API_KEY':'test',
'EVOLUTION_WEBHOOK_URL':'http://localhost/webhook/whatsapp','WHATSAPP_WEBHOOK_SECRET':'test-hook',
'APP_PUBLIC_URL':'https://test.local','ADMIN_USERNAME':'owner','ADMIN_PASSWORD':'test-password',
'SESSION_SECRET':'testing-only-secret-not-for-production',
}.items(): os.environ[key]=value
