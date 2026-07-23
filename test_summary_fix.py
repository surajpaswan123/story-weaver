import os

# Simulate the parsing logic I implemented
sections = {}
ai_response_text = """
## Incidents
- Incident 1
- Incident 2

## Summary
This is a test summary that SHOULD appear in the file.
It has multiple lines.

## Characters
- Character A
"""

current_header = None
current_lines = []

ELEMENT_CATEGORIES = ["characters", "villains", "locations", "incidents", "items"]

for line in ai_response_text.split("\n"):
    line = line.strip()
    if not line: continue
    
    header_lower = line.lower()
    
    # Check for ANY new section header (to close the previous one)
    is_new_section = False
    
    # Check for element category headers
    for cat in ELEMENT_CATEGORIES:
        if header_lower.startswith(f"## {cat}"):
            is_new_section = True
            break
    
    # Check for summary/consistency headers
    if header_lower.startswith("## summary") or header_lower.startswith("## consistency"):
        is_new_section = True

    if is_new_section:
        # Close current section
        if current_header:
            sections[current_header] = "\n".join(current_lines).strip()
        
        # Reset for new section
        current_lines = []
        current_header = None
        
        # Identify new header
        if header_lower.startswith("## summary"):
            current_header = "summary"
        elif header_lower.startswith("## consistency"):
            current_header = "consistency"
        else:
            for cat in ELEMENT_CATEGORIES:
                if header_lower.startswith(f"## {cat}"):
                    current_header = cat
                    break
        continue

    # Append content to current section
    if current_header:
        current_lines.append(line)

# Close last section
if current_header:
    sections[current_header] = "\n".join(current_lines).strip()

print(f"Captured Sections: {list(sections.keys())}")
if "summary" in sections:
    print(f"Summary Content: '{sections['summary']}'")
    with open("test_summary.md", "w", encoding="utf-8") as f:
        f.write(sections["summary"])
    print("File write successful.")
else:
    print("FAILED to capture summary.")
