new_event = data.get('new_event', '')
entity_prefix = data.get('entity_prefix', 'input_text.event')

try:
    max_events = int(data.get('max_events', 10))
except (TypeError, ValueError):
    max_events = 10

if max_events < 1:
    max_events = 1

if not new_event:
    logger.warning('shift_event_log: new_event empty; skipping')
else:
    def set_value(entity_id, value):
        hass.services.call(
            'input_text',
            'set_value',
            {
                'entity_id': entity_id,
                'value': value,
            },
            False,
        )

    for idx in range(max_events - 1, 0, -1):
        prev = hass.states.get(f"{entity_prefix}_{idx}")
        if prev is not None and prev.state not in ('unknown', 'unavailable'):
            set_value(f"{entity_prefix}_{idx + 1}", prev.state)
        else:
            set_value(f"{entity_prefix}_{idx + 1}", '')

    set_value(f"{entity_prefix}_1", new_event)
