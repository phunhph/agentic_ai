import sys
import logging
from v3.service import V3Service

# Ensure stdout uses UTF-8 to avoid UnicodeEncodeError on Windows consoles
try:
	sys.stdout.reconfigure(encoding='utf-8')
except Exception:
	pass

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(name)s: %(message)s')

svc = V3Service()
res = svc.run_pipeline('thông tin sale phunh')
print('\n=== OUTPUT ===')
print('assistant_response:', res.get('assistant_response'))
print('primary_entity:', res.get('reasoning', {}).get('primary_entity'))
print('intent:', res.get('reasoning', {}).get('intent'))
print('latency_ms:', res.get('latency_ms'))
