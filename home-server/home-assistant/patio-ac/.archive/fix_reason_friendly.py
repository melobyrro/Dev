from pathlib import Path

path = Path('/mnt/ByrroServer/docker-data/homeassistant/config/configuration.yaml')
text = path.read_text()
old = """          {% set reason = states('input_select.patio_ac_reason') %}\n              {% if trigger.entity_id == 'input_select.patio_ac_reason' %}\n                {% set reason = trigger.to_state.state %}\n              {% endif %}\n"""
if old in text:
    text = text.replace(old, "          {% set reason = states('input_select.patio_ac_reason') %}\n")
    path.write_text(text)
    print('patio_ac_reason_friendly template updated')
else:
    print('template block not found; no changes')
