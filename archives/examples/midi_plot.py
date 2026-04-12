import sys
sys.path.insert(0, r"C:\Users\mitim\Desktop\MITHIC\code\DUSTrack")
import midi

# add

midi_file_path = r"\\192.168.1.104\home\piano\data\045\disklavier\20250815_144525_pia02_s045_007_tempo_ramp_ap345.mid"
midi_log = midi.Log(midi_file_path)
signals = midi_log.to_signals(pedal_threshold=None)()
print(midi_log.duration)
print(midi_log.pm.get_end_time())

print(signals.shape)
print(signals.shape[0]/midi_log.sr)

notes = midi_log.notes