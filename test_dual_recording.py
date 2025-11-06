#!/usr/bin/env python3
"""Test dual-program manual recording for Block A (VOB) and Block E (CBC)."""

from audio_recorder import recorder
from config import Config
import threading
import time

print('=== MANUAL RECORDING TEST ===')
print('Starting 5-minute recordings for Block A (VOB) and Block E (CBC)')
print()

# Block E (CBC) - 9:00-10:00
print('📻 Block E - CBC Q100.7FM (Let\'s Talk About It)')
program_e = Config.get_program_by_block('E')
config_e = Config.get_program_config(program_e)
print(f'   Station: {config_e["station"]}')
print(f'   Stream: {config_e["stream_url"]}')
print('   Starting 5-minute recording...')

def record_e():
    result = recorder.record_live_duration('E', duration_minutes=5)
    if result:
        print(f'✅ Block E recording completed: {result}')
    else:
        print('❌ Block E recording failed')

thread_e = threading.Thread(target=record_e, daemon=False)
thread_e.start()

# Wait a moment before starting second recording
time.sleep(2)

# Block A (VOB) - 10:00-12:00
print()
print('📻 Block A - VOB 92.9FM (Down to Brass Tacks)')
program_a = Config.get_program_by_block('A')
config_a = Config.get_program_config(program_a)
print(f'   Station: {config_a["station"]}')
print(f'   Stream: {config_a["stream_url"]}')
print('   Starting 5-minute recording...')

def record_a():
    result = recorder.record_live_duration('A', duration_minutes=5)
    if result:
        print(f'✅ Block A recording completed: {result}')
    else:
        print('❌ Block A recording failed')

thread_a = threading.Thread(target=record_a, daemon=False)
thread_a.start()

print()
print('⏳ Both recordings started. They will run for 5 minutes each.')
print('   Check the audio/ directory for output files.')

# Wait for both threads to complete
thread_e.join()
thread_a.join()

print()
print('✅ Manual recording test completed!')
