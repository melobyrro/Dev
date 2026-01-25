#!/usr/bin/env python3
"""Fix duplicate YAML keys in Home Assistant configuration.yaml"""

config_path = "/mnt/ByrroServer/docker-data/homeassistant/config/configuration.yaml"

with open(config_path, "r") as f:
    lines = f.readlines()

print(f"Original file: {len(lines)} lines")

# Find the duplicate block start (around line 2834)
# It starts with "# ===========" followed by "# Plex Priority"
start_idx = None
for i, line in enumerate(lines):
    if line.strip().startswith("# ===") and i+1 < len(lines) and "Plex Priority" in lines[i+1]:
        start_idx = i
        break

if start_idx is None:
    print("Could not find Plex Priority comment block, trying alternate method...")
    # Find duplicate input_number: after line 2000
    for i, line in enumerate(lines):
        if i > 2000 and line.strip() == "input_number:":
            # Go back to find comment block start
            j = i - 1
            while j > 0 and (lines[j].strip() == "" or lines[j].strip().startswith("#")):
                j -= 1
            start_idx = j + 1
            break

print(f"Duplicate block starts at line: {start_idx + 1 if start_idx else 'Not found'}")

if not start_idx:
    print("ERROR: Could not locate duplicate block")
    exit(1)

# Keep everything before the duplicate block (but include python_script:)
# Find python_script: just before the block
python_script_idx = None
for i in range(start_idx - 1, max(0, start_idx - 5), -1):
    if lines[i].strip() == "python_script:":
        python_script_idx = i
        break

if python_script_idx:
    # Keep up to and including python_script:
    lines = lines[:python_script_idx + 2]  # +2 to include newline after
    print(f"Keeping up to line {python_script_idx + 1} (python_script:)")
else:
    lines = lines[:start_idx]
    print(f"Keeping up to line {start_idx}")

content = "".join(lines)

# Now add Plex Priority content to existing sections

# 1. Add to input_boolean (before input_text:)
input_boolean_add = '''
# Plex Priority
  plex_priority_enabled:
    name: Enable Priority Optimization
    icon: mdi:rocket
    initial: on
'''
content = content.replace("\ninput_text:", input_boolean_add + "input_text:")

# 2. Add to input_number (before sensor: which follows input_number)
input_number_add = '''
# Plex Priority
  plex_niceness:
    name: Plex Niceness
    min: -20
    max: 19
    step: 1
    icon: mdi:speedometer
    initial: -5
  qbit_niceness:
    name: qBittorrent Niceness
    min: -20
    max: 19
    step: 1
    icon: mdi:snail
    initial: 10
'''
content = content.replace("\nsensor:", input_number_add + "sensor:")

# 3. Add to input_select (before "# Boolean Helpers" or input_boolean)
input_select_add = '''
# Plex Priority
  plex_io_class:
    name: Plex I/O Class
    options:
      - "1 (Realtime)"
      - "2 (Best Effort)"
      - "3 (Idle)"
    initial: "1 (Realtime)"
  qbit_io_class:
    name: qBittorrent I/O Class
    options:
      - "1 (Realtime)"
      - "2 (Best Effort)"
      - "3 (Idle)"
    initial: "3 (Idle)"
'''
if "# Boolean Helpers\ninput_boolean:" in content:
    content = content.replace("# Boolean Helpers\ninput_boolean:", input_select_add + "# Boolean Helpers\ninput_boolean:")
elif "\n\ninput_boolean:" in content:
    content = content.replace("\n\ninput_boolean:", input_select_add + "\ninput_boolean:")

# 4. Add to shell_command (need to find what follows it)
shell_command_add = '''
# Plex Priority
  update_plex_priority_config: >
    echo "PLEX_NICENESS={{ states('input_number.plex_niceness') | int }}
    QBIT_NICENESS={{ states('input_number.qbit_niceness') | int }}
    PLEX_IONICE_CLASS={{ states('input_select.plex_io_class').split(' ')[0] }}
    QBIT_IONICE_CLASS={{ states('input_select.qbit_io_class').split(' ')[0] }}
    ENABLED={{ states('input_boolean.plex_priority_enabled') | lower }}" > /config/plex_priority.conf
'''

# Find shell_command section and the next top-level section
lines = content.split("\n")
shell_idx = None
for i, line in enumerate(lines):
    if line == "shell_command:":
        shell_idx = i
        break

if shell_idx:
    # Find next top-level section
    next_idx = None
    for i in range(shell_idx + 1, len(lines)):
        line = lines[i]
        if line and not line.startswith(" ") and not line.startswith("#") and ":" in line:
            next_idx = i
            next_section = line
            print(f"shell_command at {shell_idx+1}, next section '{next_section}' at {next_idx+1}")
            break

    if next_idx:
        lines.insert(next_idx, shell_command_add.rstrip())
        content = "\n".join(lines)

# 5. Add command_line sensors
command_line_add = '''
# Plex Priority
  - sensor:
      name: Plex Priority Status
      command: "cat /config/plex_priority.state 2>/dev/null || echo 'unknown'"
      scan_interval: 10
      unique_id: plex_priority_status
  - sensor:
      name: Plex Priority Log
      command: "tail -n 15 /config/plex_priority.log 2>/dev/null || echo 'No logs found'"
      scan_interval: 30
      unique_id: plex_priority_log
      value_template: "OK"
      json_attributes:
        - log_content
'''

# Find command_line section and add before next section
lines = content.split("\n")
cmd_idx = None
for i, line in enumerate(lines):
    if line == "command_line:":
        cmd_idx = i
        break

if cmd_idx:
    # Find next top-level section
    next_idx = None
    for i in range(cmd_idx + 1, len(lines)):
        line = lines[i]
        if line and not line.startswith(" ") and not line.startswith("#") and ":" in line:
            next_idx = i
            next_section = line
            print(f"command_line at {cmd_idx+1}, next section '{next_section}' at {next_idx+1}")
            break

    if next_idx:
        lines.insert(next_idx, command_line_add.rstrip())
        content = "\n".join(lines)

# Ensure file ends with newline
if not content.endswith("\n"):
    content += "\n"

# Write the fixed file
with open(config_path, "w") as f:
    f.write(content)

final_lines = content.count("\n")
print(f"Fixed file: {final_lines} lines")
print("Configuration file fixed successfully!")
